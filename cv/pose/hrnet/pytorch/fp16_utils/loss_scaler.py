# ------------------------------------------------------------------------------
# Based on:
# apex
# Copyright (c) NVIDIA
# Licence under The BSD 3-Clause "New" or "Revised" License
# https://github.com/NVIDIA/apex
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ------------------------------------------------------------------------------
# Copyright (c) Microsoft
# Licensed under the MIT License.
# Modified by Bowen Cheng
# ------------------------------------------------------------------------------

import torch


# item() is a recent addition, so this helps with backward compatibility.
def to_python_float(t):
    if hasattr(t, 'item'):
        return t.item()
    else:
        return t[0]


class LossScaler:
    """
    Class that manages a static loss scale.  This class is intended to interact with
    :class:`FP16_Optimizer`, and should not be directly manipulated by the user.
    Use of :class:`LossScaler` is enabled via the ``static_loss_scale`` argument to
    :class:`FP16_Optimizer`'s constructor.
    Args:
        scale (float, optional, default=1.0):  The loss scale.
    """

    def __init__(self, scale=1):
        self.cur_scale = scale

    # `params` is a list / generator of torch.Variable
    def has_overflow(self, params):
        return False

    # `x` is a torch.Tensor
    def _has_inf_or_nan(x):
        return False

    def update_scale(self, overflow):
        pass

    @property
    def loss_scale(self):
        return self.cur_scale

    def scale_gradient(self, module, grad_in, grad_out):
        return tuple(self.loss_scale * g for g in grad_in)

    def backward(self, loss):
        scaled_loss = loss * self.loss_scale
        scaled_loss.backward()


class DynamicLossScaler:
    """
    Class that manages dynamic loss scaling.  It is recommended to use :class:`DynamicLossScaler`
    indirectly, by supplying ``dynamic_loss_scale=True`` to the constructor of
    :class:`FP16_Optimizer`.  However, it's important to understand how :class:`DynamicLossScaler`
    operates, because the default options can be changed using the
    the ``dynamic_loss_args`` argument to :class:`FP16_Optimizer`'s constructor.
    Loss scaling is designed to combat the problem of underflowing gradients encountered at long
    times when training fp16 networks.  Dynamic loss scaling begins by attempting a very high loss
    scale.  Ironically, this may result in OVERflowing gradients.  If overflowing gradients are
    encountered, :class:`DynamicLossScaler` informs :class:`FP16_Optimizer` that an overflow has
    occurred.
    :class:`FP16_Optimizer` then skips the update step for this particular iteration/minibatch,
    and :class:`DynamicLossScaler` adjusts the loss scale to a lower value.
    If a certain number of iterations occur without overflowing gradients detected,
    :class:`DynamicLossScaler` increases the loss scale once more.
    In this way :class:`DynamicLossScaler` attempts to "ride the edge" of
    always using the highest loss scale possible without incurring overflow.
    Args:
        init_scale (float, optional, default=2**32):  Initial loss scale attempted by :class:`DynamicLossScaler.`
        scale_factor (float, optional, default=2.0):  Factor used when adjusting the loss scale. If an overflow is encountered, the loss scale is readjusted to loss scale/``scale_factor``.  If ``scale_window`` consecutive iterations take place without an overflow, the loss scale is readjusted to loss_scale*``scale_factor``.
        scale_window (int, optional, default=1000):  Number of consecutive iterations without an overflow to wait before increasing the loss scale.
    """

    def __init__(self,
                 init_scale=2 ** 32,
                 scale_factor=2.,
                 scale_window=1000):
        self.cur_scale = init_scale
        self.cur_iter = 0
        self.last_overflow_iter = -1
        self.scale_factor = scale_factor
        self.scale_window = scale_window

    # `params` is a list / generator of torch.Variable
    def has_overflow(self, params):
        for p in params:
            # if p.grad is not None and DynamicLossScaler._has_inf_or_nan(p.grad.data):
            #     return True
            if p.grad is not None and self._has_inf_or_nan(p.grad.data):
                return True

        return False

    # `x` is a torch.Tensor
    # def _has_inf_or_nan(x):
    def _has_inf_or_nan(self, x):
        try:
            # if x is half, the .float() incurs an additional deep copy, but it's necessary if
            # Pytorch's .sum() creates a one-element tensor of the same type as x
            # (which is true for some recent version of pytorch).
            cpu_sum = float(x.float().sum())
            # More efficient version that can be used if .sum() returns a Python scalar
            # cpu_sum = float(x.sum())
        except RuntimeError as instance:
            # We want to check if inst is actually an overflow exception.
            # RuntimeError could come from a different error.
            # If so, we still want the exception to propagate.
            if "value cannot be converted" not in instance.args[0]:
                raise
            return True
        else:
            if cpu_sum == float('inf') or cpu_sum == -float('inf') or cpu_sum != cpu_sum:
                return True
            return False

    # `overflow` is boolean indicating whether the gradient overflowed
    def update_scale(self, overflow):
        if overflow:
            # self.cur_scale /= self.scale_factor
            self.cur_scale = max(self.cur_scale / self.scale_factor, 1)
            self.last_overflow_iter = self.cur_iter
        else:
            if (self.cur_iter - self.last_overflow_iter) % self.scale_window == 0:
                self.cur_scale *= self.scale_factor
        self.cur_iter += 1

    @property
    def loss_scale(self):
        return self.cur_scale

    def scale_gradient(self, module, grad_in, grad_out):
        return tuple(self.loss_scale * g for g in grad_in)

    def backward(self, loss):
        scaled_loss = loss * self.loss_scale
        scaled_loss.backward()


##############################################################
# Example usage below here -- assuming it's in a separate file
##############################################################
"""
TO-DO separate out into an example.
if __name__ == "__main__":
    import torch
    from torch.autograd import Variable
    from dynamic_loss_scaler import DynamicLossScaler
    # N is batch size; D_in is input dimension;
    # H is hidden dimension; D_out is output dimension.
    N, D_in, H, D_out = 64, 1000, 100, 10
    # Create random Tensors to hold inputs and outputs, and wrap them in Variables.
    x = Variable(torch.randn(N, D_in), requires_grad=False)
    y = Variable(torch.randn(N, D_out), requires_grad=False)
    w1 = Variable(torch.randn(D_in, H), requires_grad=True)
    w2 = Variable(torch.randn(H, D_out), requires_grad=True)
    parameters = [w1, w2]
    learning_rate = 1e-6
    optimizer = torch.optim.SGD(parameters, lr=learning_rate)
    loss_scaler = DynamicLossScaler()
    for t in range(500):
        y_pred = x.mm(w1).clamp(min=0).mm(w2)
        loss = (y_pred - y).pow(2).sum() * loss_scaler.loss_scale
        print('Iter {} loss scale: {}'.format(t, loss_scaler.loss_scale))
        print('Iter {} scaled loss: {}'.format(t, loss.data[0]))
        print('Iter {} unscaled loss: {}'.format(t, loss.data[0] / loss_scaler.loss_scale))
        # Run backprop
        optimizer.zero_grad()
        loss.backward()
        # Check for overflow
        has_overflow = DynamicLossScaler.has_overflow(parameters)
        # If no overflow, unscale grad and update as usual
        if not has_overflow:
            for param in parameters:
                param.grad.data.mul_(1. / loss_scaler.loss_scale)
            optimizer.step()
        # Otherwise, don't do anything -- ie, skip iteration
        else:
            print('OVERFLOW!')
        # Update loss scale for next iteration
        loss_scaler.update_scale(has_overflow)
"""
