from __future__ import division

from argparse import ArgumentParser
import h5py
import logging
import os

from ont_fast5_api import CURRENT_FAST5_VERSION
from ont_fast5_api.conversion_tools.conversion_utils import get_fast5_file_list, get_progress_bar
from ont_fast5_api.fast5_file import Fast5File
from ont_fast5_api.multi_fast5 import MultiFast5File

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
exc_info = False



class EmptyFast5(Fast5File):
    def _initialise_file(self):
        # We don't want to create/validate the full f5 data structure as most fields won't exist yet
        self.handle = h5py.File(self.filename, self.mode)
        self.handle.attrs['file_version'] = CURRENT_FAST5_VERSION
        self._is_open = True


def count_reads(file_list):
    count = 0
    for filename in file_list:
        with MultiFast5File(filename, 'r') as f5:
            count += len(f5.get_read_ids())
    return count


def batch_convert_multi_files_to_single(input_path, output_folder, batch_size, recursive):
    file_list = get_fast5_file_list(input_path, recursive)
    pbar = get_progress_bar(count_reads(file_list))
    for filename in file_list:
        convert_multi_to_single(filename, output_folder, batch_size, pbar)
    pbar.finish()


def convert_multi_to_single(input_file, output_folder, batch_size, pbar):
    count = pbar.currval
    try:
        with MultiFast5File(input_file, 'r') as multi_f5:
            for read_id in multi_f5.get_read_ids():
                try:
                    subfolder = str(count // batch_size)
                    read = multi_f5.get_read(read_id)
                    output_file = os.path.join(output_folder, subfolder, "{}.fast5".format(read_id))
                    create_single_f5(output_file, read)
                    count += 1
                    pbar.update(count)
                except Exception as e:
                    logger.error("{}\n\tFailed to copy read '{}' from {}"
                                 "".format(str(e), read_id, input_file), exc_info=exc_info)
    except Exception as e:
        logger.error("{}\n\tFailed to copy files from: {}"
                     "".format(e, input_file), exc_info=exc_info)


def create_single_f5(output_file, read):
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    with EmptyFast5(output_file, 'w') as single_f5:
        for group in read.handle:
            if group == "Raw":
                read_number = read.handle["Raw"].attrs["read_number"]
                single_f5.handle.copy(read.handle[group], "Raw/Reads/Read_{}".format(read_number))
            elif group in ("channel_id", "context_tags", "tracking_id"):
                if "UniqueGlobalKey" not in single_f5.handle:
                    single_f5.handle.create_group("UniqueGlobalKey")
                single_f5.handle.copy(read.handle[group], "UniqueGlobalKey/{}".format(group))
            else:
                single_f5.handle.copy(read.handle[group], group)


def main():
    parser = ArgumentParser("")
    parser.add_argument('-i', '--input', required=True,
                        help="MultiRead fast5 file or path to directory of MultiRead files")
    parser.add_argument('-s', '--save_path', required=True,
                        help="Folder to output SingleRead fast5 files to")
    parser.add_argument('-n', '--batch_size', type=int, default=4000, required=False,
                        help="Number of reads per multi-read file")
    parser.add_argument('--recursive', action='store_true',
                        help="Search recursively through folders for for MultiRead fast5 files")
    args = parser.parse_args()

    batch_convert_multi_files_to_single(args.input, args.save_path, args.batch_size, args.recursive)


if __name__ == '__main__':
    main()
