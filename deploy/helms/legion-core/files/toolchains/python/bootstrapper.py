#!/usr/bin/bash
import argparse
import sys
import os
import subprocess
import typing
import threading
import tempfile


GIT_CHECKOUT_REPO_URI = 'GIT_CHECKOUT_REPO_URI'
GIT_CHECKOUT_REPO_REF = 'GIT_CHECKOUT_REPO_REF'
GIT_BIN = 'GIT_BIN'
GIT_CHECKOUT_SUB_FOLDER = 'GIT_CHECKOUT_SUB_FOLDER'
PYTHON_INTERPRETER = 'PYTHON_INTERPRETER'


class Arguments(typing.NamedTuple):
    toolchain: str
    entry_point: str
    arguments: typing.List[str]


class FailedStep(Exception):
    def __init__(self, exception_group: str, exit_code: int, message: typing.Optional[str]=None):
        self._exception_group: str = exception_group
        self._exit_code: int = exit_code
        self._origin_message: typing.Optional[str] = message
        self._message: str = 'Exit code: {} ({})\n{}'.format(exit_code, exception_group, message)
        super().__init__(self._message)

    @property
    def origin_message(self) -> str:
        return self._origin_message

    @property
    def exit_code(self) -> int:
        return self._exit_code

    @property
    def message(self) -> str:
        return self._message

    def __str__(self):
        return self.message

    __repr__ = __str__


class CannotFetchSourceCode(FailedStep):
    def __init__(self, message: typing.Optional[str] = None):
        super().__init__(exception_group='cannot-fetch-source-code',
                         exit_code=2,
                         message=message)


class CannotBuildModel(FailedStep):
    def __init__(self, message: typing.Optional[str] = None):
        super().__init__(exception_group='cannot-build-model',
                         exit_code=3,
                         message=message)


class CannotPushReadyModel(FailedStep):
    def __init__(self, message: typing.Optional[str] = None):
        super().__init__(exception_group='cannot-push-model',
                         exit_code=4,
                         message=message)


class GeneralFailure(FailedStep):
    def __init__(self, message: typing.Optional[str] = None):
        super().__init__(exception_group='general-failure',
                         exit_code=5,
                         message=message)


def output_current_stage(stage_name: str) -> None:
    border_size = 5
    border = '=' * border_size
    print('{} Starting stage: {} {}'.format(border, stage_name, border), flush=True)


def output_exception_and_finish(exception_info: FailedStep):
    print(exception_info.message, file=sys.__stderr__)
    sys.exit(exception_info.exit_code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser('Bootup application')
    parser.add_argument('toolchain', type=str)
    parser.add_argument('entry_point', type=str)
    parser.add_argument('tail', nargs='*')

    return parser


def run(args, cwd, shell=False) -> typing.Tuple[int, str, str]:
    if shell and hasattr(args, '__iter__'):
        args = ' '.join(args)

    out_streams_directory = tempfile.mkdtemp()
    output_stdout = os.path.join(out_streams_directory, 'stdout.log')
    output_stderr = os.path.join(out_streams_directory, 'stderr.log')

    def process_output_stream(process, stream_name, target_path):
        with open(target_path, 'wb') as out_stream:
            console_stream = getattr(sys, stream_name)
            input_stream = getattr(process, stream_name)
            while True:
                byte = input_stream.read(1)
                if byte:
                    console_stream.buffer.write(byte)
                    console_stream.flush()
                    out_stream.write(byte)
                else:
                    break

    print('Executing: {!r} with shell={!r} and cwd={!r}'.format(args, shell, cwd), flush=True)
    proc = subprocess.Popen(args,
                            cwd=cwd,
                            shell=shell,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    threading.Thread(target=process_output_stream, args=(proc, 'stdout', output_stdout)).run()
    threading.Thread(target=process_output_stream, args=(proc, 'stderr', output_stderr)).run()

    proc.wait()

    return proc.returncode, output_stdout, output_stderr


def checkout_repo(_: Arguments) -> str:
    cwd = os.getcwd()

    repo_uri = os.getenv(GIT_CHECKOUT_REPO_URI)
    if not repo_uri:
        raise CannotFetchSourceCode('Repository URI is unknown')

    repo_ref = os.getenv(GIT_CHECKOUT_REPO_REF)
    if not repo_ref:
        raise CannotFetchSourceCode('Repository REF is unknown')

    target_folder = os.path.join(cwd, os.getenv(GIT_CHECKOUT_SUB_FOLDER, 'src'))
    if os.path.exists(target_folder):
        raise CannotFetchSourceCode('Target folder for repository already exists')

    git_binary = os.getenv(GIT_BIN)
    if not git_binary:
        raise CannotFetchSourceCode('GIT binary is unset')

    print('Checking out repo {} to folder {} using'.format(repo_uri, target_folder))

    clone_command = [git_binary, 'clone', '-n', repo_uri, target_folder]
    clone_status, clone_stdout, clone_stderr = run(clone_command, cwd)

    if clone_status != 0:
        raise CannotFetchSourceCode('GIT clone failed with exit code: {}'.format(clone_status))

    reset_command = [git_binary, 'reset', '--hard', repo_ref]
    reset_status, reset_stdout, reset_stderr = run(reset_command, target_folder)
    if reset_status != 0:
        raise CannotFetchSourceCode('GIT reset failed with exit code: {}'.format(reset_status))

    return target_folder


def train_code(args: Arguments, source_code_directory: str) -> None:
    if args.toolchain != 'python':
        raise CannotBuildModel('Unknown toolchain name: {}'.format(args.toolchain))

    entry_point_file = os.path.join(source_code_directory, args.entry_point)
    if not os.path.exists(entry_point_file):
        raise CannotBuildModel('Cannot find file {} in directory {}'.format(args.entry_point, source_code_directory))

    _, ext = os.path.splitext(entry_point_file.lower())
    artifacts = []

    interpreter = os.getenv(PYTHON_INTERPRETER)
    if not interpreter:
        raise CannotBuildModel('Unknown python interpreter')

    if ext == '.ipynb':
        nb_artifact = os.path.join(source_code_directory, 'nb-result.html')
        artifacts.append(nb_artifact)
        command = ['jupyter', 'nbconvert',
                   '--to', 'html',
                   '--execute',
                   entry_point_file,
                   '--output', nb_artifact]
    elif ext in ('.py', '.pyc'):
        command = [interpreter, entry_point_file]
    else:
        raise CannotBuildModel('Unsupported extension: {}'.format(ext))

    run_status, run_stdout, run_stderr = run(command, source_code_directory, shell=True)

    if run_status != 0:
        raise CannotBuildModel('Model training returned: {}'.format(run_status))


def capture_container(_: Arguments) -> None:
    capture_status, capture_stdout, capture_stderr = run('legionctl build', os.getcwd(), shell=True)
    if capture_status != 0:
        raise CannotBuildModel('LegionCTL build returned: {}'.format(capture_status))


def work(args: Arguments) -> None:
    output_current_stage('Checking out source code')
    source_code_directory = checkout_repo(args)

    output_current_stage('Training code')
    train_code(args, source_code_directory)

    output_current_stage('Capturing code')
    capture_container(args)


def boot() -> None:
    try:
        parser = build_parser()
        args = parser.parse_args()
        args_instance = Arguments(
            toolchain=args.toolchain,
            entry_point=args.entry_point,
            arguments=args.tail,
        )
        work(args_instance)
    except FailedStep as expected_exception:
        output_exception_and_finish(expected_exception)
    except BaseException as unexpected_exception:
        general_failure = GeneralFailure(message=str(unexpected_exception))
        output_exception_and_finish(general_failure)


if __name__ == '__main__':
    boot()
