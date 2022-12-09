#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2020 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Hervé BREDIN - http://herve.niderb.fr

import yaml
from pathlib import Path
import warnings
import pandas as pd
from pyannote.core import Segment, Timeline, Annotation
from .protocol.protocol import ProtocolFile

from typing import Text
from typing import Union
from typing import Dict
from typing import List

DatabaseName = Text
PathTemplate = Text


def get_unique_identifier(item):
    """Return unique item identifier

    The complete format is {database}/{uri}_{channel}:
    * prefixed by "{database}/" only when `item` has a 'database' key.
    * suffixed by "_{channel}" only when `item` has a 'channel' key.

    Parameters
    ----------
    item : dict
        Item as yielded by pyannote.database protocols

    Returns
    -------
    identifier : str
        Unique item identifier
    """

    IDENTIFIER = ""

    # {database}/{uri}_{channel}
    database = item.get("database", None)
    if database is not None:
        IDENTIFIER += f"{database}/"
    IDENTIFIER += item["uri"]
    channel = item.get("channel", None)
    if channel is not None:
        IDENTIFIER += f"_{channel:d}"

    return IDENTIFIER


# This function is used in custom.py
def get_annotated(current_file):
    """Get part of the file that is annotated.

        Parameters
        ----------
        current_file : `dict`
            File generated by a `
    pyannote.database` protocol.

        Returns
        -------
        annotated : `pyannote.core.Timeline`
            Part of the file that is annotated. Defaults to
            `current_file["annotated"]`. When it does not exist, try to use the
            full audio extent. When that fails, use "annotation" extent.
    """

    # if protocol provides 'annotated' key, use it
    if "annotated" in current_file:
        annotated = current_file["annotated"]
        return annotated

    # if it does not, but does provide 'audio' key
    # try and use wav duration

    if "duration" in current_file:
        try:
            duration = current_file["duration"]
        except ImportError:
            pass
        else:
            annotated = Timeline([Segment(0, duration)])
            msg = '"annotated" was approximated by [0, audio duration].'
            warnings.warn(msg)
            return annotated

    extent = current_file["annotation"].get_timeline().extent()
    annotated = Timeline([extent])

    msg = (
        '"annotated" was approximated by "annotation" extent. '
        'Please provide "annotated" directly, or at the very '
        'least, use a "duration" preprocessor.'
    )
    warnings.warn(msg)

    return annotated


def get_label_identifier(label, current_file):
    """Return unique label identifier

    Parameters
    ----------
    label : str
        Database-internal label
    current_file
        Yielded by pyannote.database protocols

    Returns
    -------
    unique_label : str
        Global label
    """

    # TODO. when the "true" name of a person is used,
    # do not preprend database name.
    database = current_file["database"]
    return database + "|" + label


def load_rttm(file_rttm, keep_type="SPEAKER"):
    """Load RTTM file

    Parameter
    ---------
    file_rttm : `str`
        Path to RTTM file.
    keep_type : str, optional
        Only keep lines with this type (field #1 in RTTM specs).
        Defaults to "SPEAKER".

    Returns
    -------
    annotations : `dict`
        Speaker diarization as a {uri: pyannote.core.Annotation} dictionary.
    """

    names = [
        "type",
        "uri",
        "NA2",
        "start",
        "duration",
        "NA3",
        "NA4",
        "speaker",
        "NA5",
        "NA6",
    ]
    dtype = {"uri": str, "start": float, "duration": float, "speaker": str}
    data = pd.read_csv(
        file_rttm,
        names=names,
        dtype=dtype,
        delim_whitespace=True,
        keep_default_na=True,
    )

    annotations = dict()
    for uri, turns in data.groupby("uri"):
        annotation = Annotation(uri=uri)
        for i, turn in turns.iterrows():
            if turn.type != keep_type:
                continue
            segment = Segment(turn.start, turn.start + turn.duration)
            annotation[segment, i] = turn.speaker
        annotations[uri] = annotation

    return annotations


def load_stm(file_stm):
    """Load STM file (speaker-info only)

    Parameter
    ---------
    file_stm : str
        Path to STM file

    Returns
    -------
    annotations : `dict`
        Speaker diarization as a {uri: pyannote.core.Annotation} dictionary.
    """

    dtype = {"uri": str, "speaker": str, "start": float, "end": float}
    data = pd.read_csv(
        file_stm,
        delim_whitespace=True,
        usecols=[0, 2, 3, 4],
        dtype=dtype,
        names=list(dtype),
    )

    annotations = dict()
    for uri, turns in data.groupby("uri"):
        annotation = Annotation(uri=uri)
        for i, turn in turns.iterrows():
            segment = Segment(turn.start, turn.end)
            annotation[segment, i] = turn.speaker
        annotations[uri] = annotation

    return annotations


def load_mdtm(file_mdtm):
    """Load MDTM file

    Parameter
    ---------
    file_mdtm : `str`
        Path to MDTM file.

    Returns
    -------
    annotations : `dict`
        Speaker diarization as a {uri: pyannote.core.Annotation} dictionary.
    """

    names = ["uri", "NA1", "start", "duration", "NA2", "NA3", "NA4", "speaker"]
    dtype = {"uri": str, "start": float, "duration": float, "speaker": str}
    data = pd.read_csv(
        file_mdtm,
        names=names,
        dtype=dtype,
        delim_whitespace=True,
        keep_default_na=False,
    )

    annotations = dict()
    for uri, turns in data.groupby("uri"):
        annotation = Annotation(uri=uri)
        for i, turn in turns.iterrows():
            segment = Segment(turn.start, turn.start + turn.duration)
            annotation[segment, i] = turn.speaker
        annotations[uri] = annotation

    return annotations


def load_uem(file_uem):
    """Load UEM file

    Parameter
    ---------
    file_uem : `str`
        Path to UEM file.

    Returns
    -------
    timelines : `dict`
        Evaluation map as a {uri: pyannote.core.Timeline} dictionary.
    """

    names = ["uri", "NA1", "start", "end"]
    dtype = {"uri": str, "start": float, "end": float}
    data = pd.read_csv(file_uem, names=names, dtype=dtype, delim_whitespace=True)

    timelines = dict()
    for uri, parts in data.groupby("uri"):
        segments = [Segment(part.start, part.end) for i, part in parts.iterrows()]
        timelines[uri] = Timeline(segments=segments, uri=uri)

    return timelines


def load_lab(path, uri: str = None) -> Annotation:
    """Load LAB file

    Parameter
    ---------
    file_lab : `str`
        Path to LAB file

    Returns
    -------
    data : `pyannote.core.Annotation`
    """

    names = ["start", "end", "label"]
    dtype = {"start": float, "end": float, "label": str}
    data = pd.read_csv(path, names=names, dtype=dtype, delim_whitespace=True)

    annotation = Annotation(uri=uri)
    for i, turn in data.iterrows():
        segment = Segment(turn.start, turn.end)
        annotation[segment, i] = turn.label

    return annotation


def load_lst(file_lst):
    """Load LST file

    LST files provide a list of URIs (one line per URI)

    Parameter
    ---------
    file_lst : `str`
        Path to LST file.

    Returns
    -------
    uris : `list`
        List or uris
    """

    with open(file_lst, mode="r") as fp:
        lines = fp.readlines()
    return [line.strip() for line in lines]


def load_mapping(mapping_txt):
    """Load mapping file

    Parameter
    ---------
    mapping_txt : `str`
        Path to mapping file

    Returns
    -------
    mapping : `dict`
        {1st field: 2nd field} dictionary
    """

    with open(mapping_txt, mode="r") as fp:
        lines = fp.readlines()

    mapping = dict()
    for line in lines:
        key, value, *left = line.strip().split()
        mapping[key] = value

    return mapping


class LabelMapper(object):
    """Label mapper for use as pyannote.database preprocessor

    Parameters
    ----------
    mapping : `dict`
        Mapping dictionary as used in `Annotation.rename_labels()`.
    keep_missing : `bool`, optional
        In case a label has no mapping, a `ValueError` will be raised.
        Set "keep_missing" to True to keep those labels unchanged instead.

    Usage
    -----
    >>> mapping = {'Hadrien': 'MAL', 'Marvin': 'MAL',
    ...            'Wassim': 'CHI', 'Herve': 'GOD'}
    >>> preprocessors = {'annotation': LabelMapper(mapping=mapping)}
    >>> protocol = get_protocol('AMI.SpeakerDiarization.MixHeadset',
                                preprocessors=preprocessors)

    """

    def __init__(self, mapping, keep_missing=False):
        self.mapping = mapping
        self.keep_missing = keep_missing

    def __call__(self, current_file):

        if not self.keep_missing:
            missing = set(current_file["annotation"].labels()) - set(self.mapping)
            if missing and not self.keep_missing:
                label = missing.pop()
                msg = (
                    f'No mapping found for label "{label}". Set "keep_missing" '
                    f"to True to keep labels with no mapping."
                )
                raise ValueError(msg)

        return current_file["annotation"].rename_labels(mapping=self.mapping)


def merge_dict_inplace(
    d: dict,
    target: dict,
    allow_overwrite: bool = True,
    overwrite_exception: bool = False,
):
    """Add all changes from target to dictionary d.
    If allow_overwrite is true, it will also overwrite any value in d that's also in target.
    If set to false, the function will raise a RuntimeError if that happens.

    Parameters
    ----------
    d : dict
        Dictionary to update in place
    target : dict
        Dictionary to take updated values from
    allow_overwrite : bool, optional
        Should existing d's values be overwitten by target's values, by default True
    overwrite_exception : bool, optional
        (only has effect if allow_overwrite == False), whether or not to raise an exception when
        a d value would be overwritten by a target value.

    Raises
    ------
    RuntimeError
        Raised when allow_overwrite==False and overwrite_exception==True and one of d's keys is
        going to be overwritten.
    """
    for k, v in target.items():
        print(f"{k=}")
        if isinstance(v, dict):
            v2 = d.get(k, {})
            merge_dict_inplace(v2, v)
        else:
            if k in d and not allow_overwrite and overwrite_exception:
                raise RuntimeError(f"Trying to overwrite key {k} ({d[k]}) with {v}")
            elif k not in d or allow_overwrite:
                d[k] = v
                print(f"d[{k}] <- {v}")
