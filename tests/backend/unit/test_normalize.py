from conftest import utt

from app.ai.agents.normalize import Chunk, apply_glossary, make_chunks


def test_glossary_fixes_near_miss():
    u = apply_glossary([utt("Mình dùng Postgress nhé")], ["Postgres"])
    assert u[0].text == "Mình dùng Postgres nhé"


def test_glossary_exact_and_case_untouched():
    u = apply_glossary([utt("dung postgres di")], ["Postgres"])
    assert u[0].text == "dung postgres di"


def test_glossary_multiword_and_unrelated():
    u = apply_glossary([utt("mo Google Calender len, xong ok")], ["Google Calendar"])
    assert u[0].text == "mo Google Calendar len, xong ok"


def test_glossary_does_not_mutate_input():
    src = [utt("Postgress")]
    apply_glossary(src, ["Postgres"])
    assert src[0].text == "Postgress"


def test_chunks_overlap():
    ch = make_chunks([utt(str(i), i) for i in range(85)], size=40, overlap=5)
    assert [len(c.utterances) for c in ch] == [40, 40, 15]
    assert ch[1].utterances[0].seq == 35
    assert [c.index for c in ch] == [0, 1, 2]
    assert isinstance(ch[0], Chunk)


def test_chunks_small_and_empty():
    assert make_chunks([]) == []
    assert len(make_chunks([utt("a")])) == 1
