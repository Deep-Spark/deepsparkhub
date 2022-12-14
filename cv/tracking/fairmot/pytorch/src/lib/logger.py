# Copyright (c) 2022, Shanghai Iluvatar CoreX Semiconductor Co., Ltd.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Code referenced from https://gist.github.com/gyglim/1f8dfb1b5c82627ae3efcfbbadb9f514
import os
import time
import sys
import torch
USE_TENSORBOARD = True
try:
  import tensorboardX
  print('Using tensorboardX')
except:
  USE_TENSORBOARD = False

class Logger(object):
  def __init__(self, opt):
    """Create a summary writer logging to log_dir."""
    if not os.path.exists(opt.save_dir):
      os.makedirs(opt.save_dir)
    if not os.path.exists(opt.debug_dir):
      os.makedirs(opt.debug_dir)

    self.opt = opt
    time_str = time.strftime('%Y-%m-%d-%H-%M')

    args = dict((name, getattr(opt, name)) for name in dir(opt)
                if not name.startswith('_'))
    file_name = os.path.join(opt.save_dir, 'opt.txt')
    with open(file_name, 'wt') as opt_file:
      opt_file.write('==> torch version: {}\n'.format(torch.__version__))
      opt_file.write('==> cudnn version: {}\n'.format(
        torch.backends.cudnn.version()))
      opt_file.write('==> Cmd:\n')
      opt_file.write(str(sys.argv))
      opt_file.write('\n==> Opt:\n')
      for k, v in sorted(args.items()):
        opt_file.write('  %s: %s\n' % (str(k), str(v)))
          
    log_dir = opt.save_dir + '/logs_{}'.format(time_str)
    if USE_TENSORBOARD:
      if (opt.is_ddp==1) and (opt.local_rank==0):
        self.writer = tensorboardX.SummaryWriter(log_dir=log_dir)
      elif (opt.is_ddp==1): 
        pass
      else:
        self.writer = tensorboardX.SummaryWriter(log_dir=log_dir)
    else:
      if not os.path.exists(os.path.dirname(log_dir)):
        os.mkdir(os.path.dirname(log_dir))
      if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    if (opt.is_ddp==1) and (opt.local_rank==0):
      self.log = open(log_dir + '/log.txt', 'w')
    elif (opt.is_ddp==1):
      pass
    else:
      self.log = open(log_dir + '/log.txt', 'w')
    try:
      os.system('cp {}/opt.txt {}/'.format(opt.save_dir, log_dir))
    except:
      pass
    self.start_line = True

  def write(self, txt):
    if self.start_line:
      time_str = time.strftime('%Y-%m-%d-%H-%M')
      self.log.write('{}: {}'.format(time_str, txt))
    else:
      self.log.write(txt)  
    self.start_line = False
    if '\n' in txt:
      self.start_line = True
      self.log.flush()
  
  def close(self):
    self.log.close()
  
  def scalar_summary(self, tag, value, step):
    """Log a scalar variable."""
    if USE_TENSORBOARD:
      if (self.opt.is_ddp==1) and (self.opt.local_rank==0):
        self.writer.add_scalar(tag, value, step)
      elif (self.opt.is_ddp==1):
        pass
      else:
        self.writer.add_scalar(tag, value, step)
