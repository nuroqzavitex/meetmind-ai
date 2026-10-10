import io
import unicodedata

import pytest
from docx import Document
from tests.backend.unit_helpers import fixture_bytes

from app.ai.errors import TranscriptParseError
from app.ai.parsing import parse_transcript

SRT = fixture_bytes("basic.srt")
VTT = fixture_bytes("basic.vtt")


def test_txt_basic():
    u = parse_transcript("a.txt", b"[00:00:05] Lan: Xin chao\n[00:00:20] Minh: Chao chi\n")
    assert [x.id for x in u] == ["u0000", "u0001"]
    assert (u[0].speaker, u[0].start, u[0].end, u[0].text) == ("Lan", 5, 20, "Xin chao")
    assert u[1].end is None


def test_txt_fixture():
    u = parse_transcript("basic.txt", fixture_bytes("basic.txt"))
    assert [x.seq for x in u] == [0, 1, 2]
    assert u[2].start == 62


def test_txt_dirty_bom_crlf_continuation():
    data = "﻿[00:00:05] Lan: Dong mot\r\n\r\ntiep tuc dong mot\r\n[00:00:09] Hoa: Hai\r\n".encode()
    u = parse_transcript("a.txt", data)
    assert len(u) == 2 and u[0].text == "Dong mot tiep tuc dong mot"
    assert parse_transcript("dirty.txt", fixture_bytes("dirty.txt"))[0].text == u[0].text


def test_txt_no_speaker_is_unknown():
    assert parse_transcript("a.txt", b"[00:00:05] chi la loi noi")[0].speaker == "Unknown"


def test_srt_and_vtt_speaker():
    assert parse_transcript("a.srt", SRT)[0].speaker == "Lan"
    assert parse_transcript("a.vtt", VTT)[0].speaker == "Minh"  # <v Minh>


def test_srt_details():
    u = parse_transcript("a.srt", SRT)
    assert (u[0].start, u[0].end, u[0].text) == (1.0, 4.5, "Xin chao")
    assert u[1].text == "Chao chi va moi nguoi"


def test_vtt_details():
    u = parse_transcript("A.VTT", VTT)
    assert [x.speaker for x in u] == ["Minh", "Lan", "Unknown"]
    assert (u[1].start, u[1].end, u[1].text) == (5.0, 8.0, "Chao anh")


def test_docx(docx_bytes):
    u = parse_transcript("a.docx", docx_bytes)
    assert u[0].speaker == "Lan"
    assert len(u) == 2 and u[0].end == 20


@pytest.mark.parametrize(
    "name,data",
    [
        ("a.pdf", b"x"),
        ("a.txt", b""),
        ("a.txt", b"\xff\xfe\x00"),
        ("a.srt", b"garbage"),
        ("a.docx", b"not a zip"),
    ],
)
def test_parse_errors(name, data):
    with pytest.raises(TranscriptParseError):
        parse_transcript(name, data)


def test_nfd_input_normalized_to_nfc():
    line = "[00:00:05] Lan Hương: Chốt dùng Postgres nhé"
    nfd = unicodedata.normalize("NFD", line)
    nfc = unicodedata.normalize("NFC", line)
    u = parse_transcript("a.txt", nfd.encode())
    assert (u[0].speaker, u[0].text) == ("Lan Hương", "Chốt dùng Postgres nhé")
    assert u[0].text == unicodedata.normalize("NFC", u[0].text)
    doc = Document()
    doc.add_paragraph(nfd)
    buf = io.BytesIO()
    doc.save(buf)
    d = parse_transcript("a.docx", buf.getvalue())
    assert f"[00:00:05] {d[0].speaker}: {d[0].text}" == nfc
