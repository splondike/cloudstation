"""
Functions for working with the templates/ directory
"""

import os
import pathlib
from string import Template


def build_template(template_file, params={}) -> str:
    """
    Returns a string containing the contents of the template_file in the
    templates directory with params substituted in.
    """

    basedir = pathlib.Path(__file__).parent.absolute()
    with open(os.path.join(basedir, 'templates', template_file), 'r') as fh:
        template = Template(fh.read())

    return template.substitute(**params)
