// Copyright (c) OpenMMLab. All rights reserved
#include "pytorch_cuda_helper.hpp"
#include "sigmoid_focal_loss_cuda_kernel.cuh"

void SigmoidFocalLossForwardCUDAKernelLauncher(Tensor input, Tensor target,
                                               Tensor weight, Tensor output,
                                               const float gamma,
                                               const float alpha) {
  int output_size = output.numel();
  int num_classes = input.size(1);
  AT_ASSERTM(target.max().item<int64_t>() <= (int64_t)num_classes,
             "target label should smaller or equal than num classes");
  at::cuda::CUDAGuard device_guard(input.device());
  cudaStream_t stream = at::cuda::getCurrentCUDAStream();
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(
      input.scalar_type(), "sigmoid_focal_loss_forward_cuda_kernel", [&] {
        sigmoid_focal_loss_forward_cuda_kernel<scalar_t>
            <<<GET_BLOCKS(output_size), THREADS_PER_BLOCK, 0, stream>>>(
                output_size, input.data_ptr<scalar_t>(),
                target.data_ptr<int64_t>(), weight.data_ptr<scalar_t>(),
                output.data_ptr<scalar_t>(), gamma, alpha, num_classes);
      });

  AT_CUDA_CHECK(cudaGetLastError());
}

void SigmoidFocalLossBackwardCUDAKernelLauncher(Tensor input, Tensor target,
                                                Tensor weight,
                                                Tensor grad_input,
                                                const float gamma,
                                                const float alpha) {
  int output_size = grad_input.numel();
  int num_classes = input.size(1);

  at::cuda::CUDAGuard device_guard(grad_input.device());
  cudaStream_t stream = at::cuda::getCurrentCUDAStream();
  AT_DISPATCH_FLOATING_TYPES_AND_HALF(
      input.scalar_type(), "sigmoid_focal_loss_backward_cuda_kernel", [&] {
        sigmoid_focal_loss_backward_cuda_kernel<scalar_t>
            <<<GET_BLOCKS(output_size), THREADS_PER_BLOCK, 0, stream>>>(
                output_size, input.data_ptr<scalar_t>(),
                target.data_ptr<int64_t>(), weight.data_ptr<scalar_t>(),
                grad_input.data_ptr<scalar_t>(), gamma, alpha, num_classes);
      });

  AT_CUDA_CHECK(cudaGetLastError());
}