import sys
import subprocess
import os
import os.path as ospath
from argparse import ArgumentParser


MODEL_DIR = ospath.abspath(
    ospath.join(
        __file__,
        "../../../"
    )
)

MODEL = ospath.basename(MODEL_DIR)

PROJ_DIR = ospath.abspath(
    ospath.join(
        MODEL_DIR,
        "pytorch"
    )
)


def _parse_known_args(parser, *args, **kwargs):
    return parser.parse_known_args(*args, **kwargs)


def parse_args():
    parser = ArgumentParser(description="PyTorch distributed training launch "
                                        "helper utilty that will spawn up "
                                        "multiple distributed processes")

    # Optional arguments for the launch helper
    parser.add_argument("--nnodes", type=int, default=1,
                        help="The number of nodes to use for distributed "
                             "training")
    parser.add_argument("--node_rank", type=int, default=0,
                        help="The rank of the node for multi-node distributed "
                             "training")
    parser.add_argument("--nproc_per_node", type=int, default=1,
                        help="The number of processes to launch on each node, "
                             "for GPU training, this is recommended to be set "
                             "to the number of GPUs in your system so that "
                             "each process can be bound to a single GPU.")
    parser.add_argument("--master_addr", default="127.0.0.1", type=str,
                        help="Master node (rank 0)'s address, should be either "
                             "the IP address or the hostname of node 0, for "
                             "single node multi-proc training, the "
                             "--master_addr can simply be 127.0.0.1")
    parser.add_argument("--master_port", default=29500, type=int,
                        help="Master node (rank 0)'s free port that needs to "
                             "be used for communciation during distributed "
                             "training")
    parser.add_argument('--no_hyperthreads', action='store_true',
                        help='Flag to disable binding to hyperthreads')
    parser.add_argument('--no_membind', action='store_true',
                        help='Flag to disable memory binding')

    # non-optional arguments for binding
    parser.add_argument("--nsockets_per_node", type=int, required=True,
                        help="Number of CPU sockets on a node")
    parser.add_argument("--ncores_per_socket", type=int, required=True,
                        help="Number of CPU cores per socket")

    # positional
    parser.add_argument("training_script", type=str,
                        help="The full path to the single GPU training "
                             "program/script to be launched in parallel, "
                             "followed by all the arguments for the "
                             "training script")

    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--name", type=str, required=True)

    args, training_script_args = _parse_known_args(parser)
    args.training_script_args = training_script_args

    return args


def get_cuda_visible_devices(gpus=1):
    if "CUDA_VISIBLE_DEVICES" in os.environ:
        return os.environ['CUDA_VISIBLE_DEVICES']
    return ','.join([str(gpu_id) for gpu_id in range(gpus)])


def main():
    args = parse_args()
    config_full_name = f"config_{args.config}.py"
    config_path = ospath.join(PROJ_DIR, args.name, "config", config_full_name)

    _, args.nnodes, args.nproc_per_node = args.config.split("x")

    args.nnodes = int(args.nnodes)
    args.nproc_per_node = int(args.nproc_per_node)

    # variables for numactrl binding

    NSOCKETS = args.nsockets_per_node
    NGPUS_PER_SOCKET = (args.nproc_per_node // args.nsockets_per_node) + (1 if (args.nproc_per_node % args.nsockets_per_node) else 0)
    NCORES_PER_GPU = args.ncores_per_socket // NGPUS_PER_SOCKET
    NCORES_PER_GPU_REMAIN=args.ncores_per_socket - NGPUS_PER_SOCKET*NCORES_PER_GPU

    # world size in terms of number of processes
    dist_world_size = args.nproc_per_node * args.nnodes

    # set PyTorch distributed related environmental variables
    current_env = os.environ.copy()
    current_env["MASTER_ADDR"] = args.master_addr
    current_env["MASTER_PORT"] = str(args.master_port)
    current_env["WORLD_SIZE"] = str(dist_world_size)
    current_env["NODE_RANK"] = str(args.node_rank)
    current_env["CUDA_VISIBLE_DEVICES"] = get_cuda_visible_devices(args.nproc_per_node)

    processes = []

    for local_rank in range(0, args.nproc_per_node):
        # each process's rank
        dist_rank = args.nproc_per_node * args.node_rank + local_rank
        current_env["RANK"] = str(dist_rank)
        current_env["LOCAL_RANK"] = str(local_rank)

        # Instead of binding to a set of cores which this task has exclusive access to,
        #   bind to all cores on the local NUMA node (may share them with other ranks)
        local_node = local_rank // NGPUS_PER_SOCKET
        numactlargs = ["--cpunodebind={}".format(local_node)]

        ## form numactrl binding command
        cpu_ranges = [local_rank * NCORES_PER_GPU,
                     (local_rank + 1) * NCORES_PER_GPU - 1,
                     local_rank * NCORES_PER_GPU + ((NCORES_PER_GPU * NGPUS_PER_SOCKET+NCORES_PER_GPU_REMAIN) * NSOCKETS),
                     (local_rank + 1) * NCORES_PER_GPU + ((NCORES_PER_GPU * NGPUS_PER_SOCKET+NCORES_PER_GPU_REMAIN) * NSOCKETS + NCORES_PER_GPU_REMAIN) - 1]

        numactlargs = []
        if args.no_hyperthreads:
            numactlargs += [ "--physcpubind={}-{}".format(*cpu_ranges[0:2]) ]
        else:
            numactlargs += [ "--physcpubind={}-{},{}-{}".format(*cpu_ranges) ]

        if not args.no_membind:
            memnode = local_rank // NGPUS_PER_SOCKET
            numactlargs += [ "--membind={}".format(memnode) ]

        # spawn the processes
        cmd = [ "/usr/bin/numactl" ] \
            + numactlargs \
            + [ sys.executable,
                "-u",
                args.training_script,
                "--local_rank={}".format(local_rank)
              ] \
            + args.training_script_args + [f"{config_path}"]

        print("=" * 80)
        print("= numactlargs_flag")
        print(cmd)
        print("=" * 80)
        process = subprocess.Popen(cmd, env=current_env)
        processes.append(process)

    for process in processes:
        process.wait()


if __name__ == "__main__":
    main()

