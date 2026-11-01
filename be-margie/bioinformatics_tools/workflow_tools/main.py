'''
Command line entrypoint for workflows
TODO: Need to match the test.smk to the command line dane_wf test, not the type
'''
import logging
import sys

from bioinformatics_tools.caragols.logger import config_logging_for_app
from bioinformatics_tools.workflow_tools import cli_flags
from bioinformatics_tools.workflow_tools.workflow import WorkflowBase

LOGGER = logging.getLogger(__name__)

# snakemake_files = [f.rsplit('.', 1)[0] for f in os.listdir(os.path.dirname(__file__)) if f.endswith('.smk')]
# snakemake_files = [x for x in snakemake_files if x not in ['main', 'Binning', 'Annotate', 'Alignment']]


def find_wf(args: list) -> None | str:
    '''
    This function takes in a list of arguments and determines what type of file
    it is. It then returns the class that can handle that file.
    '''
    type_ = None
    for cnt, arg in enumerate(args):
        if arg.startswith('wf:'):
            type_ = args[cnt + 1]
            type_ = type_.lower()
            break
    return type_


def cli():
    '''Command line interface for the script.
    '''
    # --input, --output, --working-directory and --config, as the key: value words read below.
    if cli_flags.wants_help(sys.argv[1:]):
        print(cli_flags.HELP)
        sys.exit(0)
    try:
        sys.argv[1:] = cli_flags.to_words(sys.argv[1:])
    except cli_flags.FlagError as err:
        print(f'dane_wf: {err}\n{cli_flags.HELP}', file=sys.stderr)
        sys.exit(2)

    # Step 0 - Configure Logging
    config_logging_for_app()

    data = WorkflowBase()
    # data.run_workflow()
    data.run()
    return None

    # if any(arg in sys.argv for arg in ("help", "Help", "HELP")):
    #     LOGGER.info('🆘 Help requested')
    #     LOGGER.info('The following file types are recognized and can be specified via the command line\n\033[92mdane type: <file_type>\033[0m')


if __name__ == "__main__":
    cli()
