#!/bin/python3
import argparse
from math import ceil

import numpy
import os
import pathlib
import struct
import sys
import textwrap
import typing

# Import custom modules
from .lib.print_progressbar import print_progressbar

# Allow for multiple data types from header DATA_TYPE.
DATA_TYPES = {'FLOATING_POINT': {'unpack_char': 'f', 'bytes': 4},
              'SHORT_INTEGER': {'unpack_char': 'h', 'bytes': 2}}


class ReadRPC(object):
    """
    Read RPC III files.
    A RPC III file is a data  file conforming to the RPC III  file specification developed by MTS corporation.

    In this implementation the full data structure of the RPC file is NOT supported.

    TODO:
        Support demultiplexed data format. Here it is assumed that only one frame exist in every group but this is
        generally not the case.

    Niklas Melin
    2022-02-26
    """

    def __init__(self, _file: typing.Union[str, pathlib.Path], extra_headers: dict = None, debug: bool = False):

        if extra_headers is None:
            extra_headers = []
        self.debug: bool = debug
        self.headers: dict = dict()
        self.channels: dict = dict()
        self.data: typing.Optional[numpy.array] = None
        self.time: typing.Optional[numpy.array] = None
        self.__data_type__: typing.Optional[str] = None
        self.__file_size__: typing.Optional[int] = None
        self.__headers_read__: bool = False
        self.__data_read__: bool = False
        self.__extra_headers__: dict = dict()

        # Standard integer full scale
        self.integer_standard_full_scale = 32768

        # Check received _file
        if not isinstance(_file, pathlib.Path):
            _file = pathlib.Path(_file)
        if not _file.is_file():
            sys.exit("ERROR: The RPC test data file is invalid")
        self.file = _file

        try:
            for header_name, header_value in extra_headers:
                self.__extra_headers__[header_name.upper()] = header_value.upper()
        except Exception:
            if 'header_name' in locals() and 'header_value' in locals():
                msg = 'ERROR: Additional headers could not be interpreted!' \
                      f'\n\t Header name:  {header_name}' \
                      f'\n\t Header value: {header_value}'
            else:
                msg = 'ERROR: Header data could not be interpreted! Check input...'
            sys.exit(msg)

        # Open _file handle
        with open(self.file, 'rb') as file_handle:
            # Get _file size
            file_handle.seek(0, os.SEEK_END)
            self.__file_size__ = file_handle.tell()

            # Reposition to start of _file
            file_handle.seek(0, 0)

    def __read_header__(self, file_handle):
        def __header__():
            try:
                # Read header
                __head__, __value__ = struct.unpack('<32s96s', file_handle.read(128))
                __value__ = __value__.replace(b'\0', b'').decode('windows-1252').replace('\n', '')
                __head__ = __head__.replace(b'\0', b'').decode('windows-1252').replace('\n', '')
                return __head__, __value__
            except struct.error:
                sys.exit('ERROR: Header of the file does not contain sufficient data to read 128 bytes')
            except UnicodeDecodeError:
                sys.exit('ERROR: Header of the file could not be decoded properly, exiting!')

        # Read first three records, which are mandatory and also position sensitive
        print(f' Reading headers from:\n\tFile: {self.file.as_posix()}')
        # Read the first position fixed headers
        for i in range(3):
            head_name, head_value = __header__()
            if head_name not in ['FORMAT', 'NUM_HEADER_BLOCKS', 'NUM_PARAMS']:
                sys.exit('ERROR: Header of the file does not contain required fields')

            if head_name in ['NUM_HEADER_BLOCKS', 'NUM_PARAMS']:
                self.headers[head_name] = int(head_value)
            else:
                self.headers[head_name] = head_value
            if self.debug:
                print(f'\t {head_name:18s}: {head_value}')

        # Check if _file contains data
        if not self.headers['NUM_PARAMS'] > 3:
            sys.exit('ERROR: No data in file')

        # Read all remaining headers
        for channel in range(3, self.headers['NUM_PARAMS']):
            head_name, head_value = __header__()
            # Stored in blocks of 4 (512 bytes divided into 128 byte chunks), hence at the end empty headers can appear
            if len(head_name) != 0:
                self.headers[head_name] = head_value
                if self.debug:
                    print(f"\t\t {head_name:32s}  -- {head_value}")

        # Set current position in _file
        self.header_end = file_handle.tell()

        # Add additional headers
        for header_name, head_value in self.__extra_headers__.items():
            if header_name not in self.headers:
                print(f' Adding extra header\n\t{header_name} - {head_value}')
                self.headers[header_name] = head_value
            else:
                print(f' WARNING: Extra header already defined in RPC file, skipping\n\t {header_name} - {head_value}')

        # Convert values to correct types
        try:
            self.headers['NUM_HEADER_BLOCKS'] = int(self.headers['NUM_HEADER_BLOCKS'])
            self.headers['CHANNELS'] = int(self.headers['CHANNELS'])
            self.headers['DELTA_T'] = float(self.headers['DELTA_T'])
            self.headers['PTS_PER_FRAME'] = int(self.headers['PTS_PER_FRAME'])
            self.headers['PTS_PER_GROUP'] = int(self.headers['PTS_PER_GROUP'])
            self.headers['FRAMES'] = int(self.headers['FRAMES'])
            self.__data_type__ = self.headers['DATA_TYPE']

            # Require INT_FULL_SCALE only if DATA_TYPE is SHORT_INTEGER
            if self.__data_type__ == 'SHORT_INTEGER':
                self.headers['INT_FULL_SCALE'] = int(self.headers['INT_FULL_SCALE'])

        except KeyError as expected_header:
            sys.exit(f'ERROR: A mandatory header is missing: {expected_header}')

        # Structure channel data structure
        for channel in range(int(self.headers['CHANNELS'])):
            try:
                self.channels[channel] = {}
                self.channels[channel]['Channel'] = 'Channel_' + repr(channel + 1).zfill(3)
                self.channels[channel]['Description'] = self.headers['DESC.CHAN_' + repr(channel + 1)]
                self.channels[channel]['LowerLimit'] = self.headers['LOWER_LIMIT.CHAN_' + repr(channel + 1)]
                self.channels[channel]['Scale'] = float(self.headers['SCALE.CHAN_' + repr(channel + 1)])
                self.channels[channel]['Units'] = self.headers['UNITS.CHAN_' + repr(channel + 1)]
                self.channels[channel]['UpperLimit'] = self.headers['UPPER_LIMIT.CHAN_' + repr(channel + 1)]
                if 'PART.NCHAN_' + repr(channel + 1) in self.headers:
                    self.channels[channel]['NumberInPartition'] = self.headers['PART.NCHAN_' + repr(channel + 1)]
            except KeyError as missing_key:
                print(f' Skipping: {missing_key}')
                continue

        # Indicate that the header was successfully read
        self.__headers_read__ = True

    def __read_data__(self, file_handle):
        if not self.__headers_read__:
            print(' ERROR: No header has been read, hence data structure unknown!')
            return

        channels = self.headers['CHANNELS']
        point_per_frame = self.headers['PTS_PER_FRAME']
        point_per_group = self.headers['PTS_PER_GROUP']
        frames = self.headers['FRAMES']

        # Pre-allocate a numpy array
        self.data = numpy.zeros([frames * point_per_frame, channels])

        # Read after end of header which occurs at 512 bytes times number of header blocks
        file_handle.seek(self.headers['NUM_HEADER_BLOCKS'] * 512, 0)

        # Recreate structure of demultiplexed data
        frames_per_group = int((point_per_group / point_per_frame))
        number_of_groups = int(ceil(frames / frames_per_group))
        data_order = list()
        frame_no = 1

        for i in range(number_of_groups):
            if frame_no > frames:
                break
            temp = list()
            for j in range(frames_per_group):
                if frame_no > frames:
                    break
                temp.append(frame_no)
                frame_no += 1
            data_order.append(temp)
        del temp, frame_no

        # if self.debug:
        if True:
            print(' Data structure summery:'
                  f'\n\tChannels to read:  {channels}'
                  f'\n\tPoints per frame:  {point_per_frame}'
                  f'\n\tPoints per group:  {point_per_group}'
                  f'\n\tNumber of frames:  {frames}'
                  f'\n\tNumber of groups:  {number_of_groups}'
                  f"\n\tHeader end at:     {self.headers['NUM_HEADER_BLOCKS'] * 512} bytes"
                  f"\n\tFile end at:       {self.__file_size__}"
                  f"\n\tBytes to read:     {self.__file_size__ - self.headers['NUM_HEADER_BLOCKS'] * 512}")

            print(f' Frame grouping array:\n {data_order}')
            print(f" Binary decoding settings: <{point_per_frame}{DATA_TYPES[self.__data_type__]['unpack_char']}, "
                  f"{point_per_frame * DATA_TYPES[self.__data_type__]['bytes']}, "
                  f" Bytes per data value: {DATA_TYPES[self.__data_type__]['bytes']}")

        # Check that data type matches file size
        actual_data_size = self.__file_size__ - self.headers['NUM_HEADER_BLOCKS'] * 512
        expected_data_size = point_per_frame * DATA_TYPES[self.__data_type__]['bytes'] * \
            frames_per_group * number_of_groups * channels

        if actual_data_size != expected_data_size:
            print(' ERROR: DATA_TYPE problem - Data cant be decoded correctly'
                  f'\n\tActual data size in bytes:   {actual_data_size}'
                  f'\n\tExpected data size in bytes: {expected_data_size}'
                  f'\n\tVerify that {self.__data_type__} is correct ')
            sys.exit('ERROR: DATA_TYPE error')

        # Print progress bar
        print(f'\n Reading test data from {channels} channels,')
        print_progressbar(0, frames, prefix='Progress:', suffix='Complete', length=50)

        for frame_group in data_order:
            # print(f'\t Frame: {frame + 1} of {frames}')
            for channel in range(channels):
                for frame in frame_group:
                    data = struct.unpack(f'<{point_per_frame}' + DATA_TYPES[self.__data_type__]['unpack_char'],
                                         file_handle.read(point_per_frame * DATA_TYPES[self.__data_type__]['bytes']))

                    r1 = (frame - 1) * point_per_frame
                    r2 = frame * point_per_frame
                    self.data[r1:r2, channel] = data

            print_progressbar(frame, frames, prefix='Progress:', suffix='Complete', length=50)

        # Scale channel data - valid only if DATA_TYPE is SHORT_INTEGER
        if self.__data_type__ == 'SHORT_INTEGER':
            for channel in range(channels):
                # Channel scale
                channel_scale = self.channels[channel]['Scale']
                # Standard integer full scale
                int_standard_full_scale = self.integer_standard_full_scale
                # RPC integer full scale
                int_rpc_full_scale = self.headers['INT_FULL_SCALE']

                # Compute scale factor
                scale_factor = int_rpc_full_scale / int_standard_full_scale * channel_scale

                # Scale data
                self.data[:, channel] = self.data[:, channel] * scale_factor

        # Create matching time history array
        self.time = numpy.arange(1, frames * point_per_frame + 1, dtype=numpy.float32) * self.headers['DELTA_T']

        # Indicate that the data has been read
        self.__data_read__ = True

    def import_rpc_data_from_file(self):

        # Open _file handle
        with open(self.file, 'rb') as file_handle:
            # Read headers
            self.__read_header__(file_handle)
            # Read data
            self.__read_data__(file_handle)

    def save_npy_data_to_file(self, overwrite=False):

        file_path_data = self.file.with_suffix('.npz')

        if file_path_data.is_file() and not overwrite:
            print(f' ERROR: A numpy result file exists and over write mode is: {overwrite}')
            return
        data = self.data
        times = self.time
        headers = self.headers
        channels = self.channels
        numpy.savez(file_path_data,
                    data=data,
                    time=times,
                    headers=headers,
                    channels=channels)

        print(f' Data was exported to _file: {file_path_data.as_posix()}')

    def import_npy_data_from_file(self):

        #
        file_path_data = self.file.with_suffix('.npz')

        if not file_path_data.is_file():
            print(f' ERROR: Numpy .npz was not found: {file_path_data.as_posix()}')
            return

        npz_file = numpy.load(file_path_data, allow_pickle=True)
        self.data = npz_file['data']
        self.time = npz_file['time']
        # Get numpy pickled data and convert back to dict
        self.headers = npz_file['headers'].tolist()
        self.channels = npz_file['channels'].tolist()

        print(f' Imported data of sizes: \n\tdata: {self.data.shape}\n\ttime: {self.time.shape}')

        # Set data available
        self.__data_read__ = True
        self.__headers_read__ = True

        print(f' Data was imported from _file: {file_path_data.as_posix()}')

    def get_data(self) -> typing.Union[numpy.array, bool]:
        if not self.__data_read__:
            print(' ERROR: No data has been read!')
            return False
        return self.data

    def get_time(self) -> typing.Union[typing.Tuple[numpy.array, float], bool]:
        if not self.__data_read__:
            print(' ERROR: No data has been read!')
            return False

        return self.time, self.time[-1]

    def get_data_size(self) -> typing.Union[typing.Tuple[int], bool]:
        if not self.__data_read__:
            print(' ERROR: No data has been read!')
            return False
        return self.data.shape

    def get_channels(self) -> typing.Union[int, bool]:
        if not self.__headers_read__:
            print(' ERROR: No data loaded')
            return False
        return self.channels

    def get_headers(self) -> typing.Union[dict, bool]:
        if not self.__headers_read__:
            print(' ERROR: No data loaded')
            return False
        return self.headers

    def print_channel_header_data(self):
        if not self.__headers_read__:
            print(' ERROR: No data loaded')
            return False

        for channel, data in self.channels.items():
            print(f' Channel: {channel + 1}')
            for key, value in data.items():
                print(f' \t {key:20s} : {value}')


def main():
    def argparse_check_file(_file):
        """
        'Type' for argparse - checks that file exists
        """
        # If = is in the path, split and use the right side only
        if '=' in _file:
            _file = _file.split('=')[1]
        _file = pathlib.Path(_file)
        if not _file.is_file():
            # Argparse uses the ArgumentTypeError to give a rejection message like:
            # error: argument input: x does not exist
            raise argparse.ArgumentTypeError("{0} is not a valid file".format(_file.as_posix()))
        return _file

    # Set-up parsing of input arguments
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''

             Description:
             -----------------------------------------------------------------------------------------------------------
             Application for reading RPC 3 data files into numpy arrays. In the command line version, the provided file
             is converted into a numpy .npz file. To load the data use the numpy.load module which will load the numpy
             data as a dictionary with the following keys:

                header   - Header data
                time     - Time array
                channels - Channel data
                data     - The actual measurement data

             Written by: Niklas Melin
             Syntax examples:
                rpc_reader my_data_file.rpc
                rpc_reader my_data_file.tim -header DATA_TYPE SHORT_INTEGER -header INFO_TEXT ADD_NOTE_TO_DATA
             '''))

    parser.add_argument("input_path",
                        type=argparse_check_file,
                        metavar='INPUT_PATH',
                        help="Select file containing something important \
                              \n\t  /path/to/my/input/file.rpc")
    parser.add_argument('-e', '--extra-header', action='append', nargs=2,
                        metavar=('name', 'value'), help='Set missing header and value. Repeated usage allowed!')
    parser.add_argument("--debug", "--d",
                        action="store_true",
                        default=False,
                        help="If debug is set, significant additional output is requested.\n")

    # Parse arguments into a dictionary
    cmd_line_args = vars(parser.parse_args())

    # Get arguments
    print(cmd_line_args.items())
    input_path = cmd_line_args['input_path']
    if 'extra_header' in cmd_line_args:
        extra_headers = cmd_line_args['extra_header']
    else:
        extra_headers = None
    debug = cmd_line_args['debug']

    # Start batch process
    reader_object = ReadRPC(input_path, extra_headers=extra_headers, debug=debug)
    reader_object.import_rpc_data_from_file()
    reader_object.save_npy_data_to_file()


if __name__ == '__main__':
    main()
