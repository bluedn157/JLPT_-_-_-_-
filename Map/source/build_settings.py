"""Flash arithmetic build settings for the Yeongaesomun v1.1.6 map."""
from typing import Dict
import inspect
import codecs
import re
import csv
import io
from eudplib import *
from main import settings


ESCAPE_SEQUENCE_RE = re.compile(r"(\\x..)|(\\n)")


def decode_match(match):
    return codecs.decode(match.group(0), "unicode-escape")


def escape_hex_newline(value):
    return ESCAPE_SEQUENCE_RE.sub(decode_match, value)


def init():
    # EUDDraft injects chatEvent through its plugin configuration.
    for frame_info in inspect.stack():
        if frame_info.function == 'loadPluginsFromConfig':
            chat_event_settings: Dict[str, str] = frame_info.frame.f_locals['config']['chatEvent']
            break
    else:
        raise RuntimeError("build_settings.py must be loaded by EUDDraft")

    # Restore the original map sound files configured in build.eds.
    for effect_file_name in (
        'opening_sound_1', 'opening_sound_2', 'click_sound',
        'skip_sound', 'correct_sound', 'buzzer'
    ):
        if effect_file_name not in settings:
            continue
        with open(f"effect/{settings[effect_file_name]}", 'rb') as f:
            MPQAddFile(effect_file_name, f.read())


# Legacy exports retained for the original opening and MusicSetting modules.
leaderboard_text = escape_hex_newline(settings["leaderboard_text"])
AnswerKey = EUDArray([EUDArray([0])])
MusicHint1 = EUDArray([0])
MusicHint2 = EUDArray([0])
MusicLength = EUDArray([1])
MusicAnswer = EUDArray([0])
MusicNumber = 1
MusicStart = 0
MusicEnd = 0
VoteNum = EUDArray([1, 2, 2, 3, 3, 4, 4])
EndingMusic = 1
SegmentCount = EUDArray([0, 0])
CategoryCount = 0
CategoryNames = EUDArray([0])
CategoryDescriptions = EUDArray([0])
CategoryMusics = EUDArray([EUDArray([0])])
MinQuestionLength = 1
settingName3 = Db("힌트1")
settingName4 = Db("힌트2")


# ===========================================================================
# 문제 데이터: Map/questions.csv 를 빌드할 때 읽어서 게임에서 쓰는 배열로 만듭니다.
# 문제를 추가할 때는 questions.csv에 줄만 추가하면 되고, 코드는 고칠 필요가 없습니다.
#
# 칸 순서: 난이도, 예문, 단어, 정답, 오답1, 오답2, 오답3, 뜻, 오답4, 오답5, 오답6, (메모...)
#  - 오답1~3 : 선지 세트 A,  오답4~6 : 선지 세트 B. 문제가 나올 때마다 둘 중 하나가 무작위로 나옵니다.
#              오답4~6을 비워 두면 세트 A만 나옵니다. (채울 때는 3칸 모두 채워야 합니다.)
#  - 난이도 : 초급 또는 고급
#  - 예문   : 단어가 그대로 들어 있어야 합니다. (게임에서 그 단어가 색칠되어 나옵니다.)
#  - 정답   : 단어의 올바른 읽기. 보기 순서는 게임에서 매번 자동으로 섞입니다.
#  - 뜻     : 정답 공개 때 "단어 = 뜻"으로 표시됩니다.
# 첫 줄은 제목 줄이라 읽지 않고, 칸 맨 앞이 #으로 시작하는 줄은 메모로 보고 건너뜁니다.
# ===========================================================================
QUESTION_FILE = "questions.csv"
LEVEL_CODES = {"초급": 0, "고급": 1, "0": 0, "1": 1}
LEVEL_LABELS = ("초급", "고급")
MAX_SENTENCE_LENGTH = 24    # 예문이 이 글자 수보다 길면 빌드할 때 경고만 보여줍니다.
HIGHLIGHT_ON = "\x07"       # 읽기를 묻는 단어를 색칠하는 색 코드
HIGHLIGHT_OFF = "\x04"
NOTE_READING_COLOR = "\x1F"   # 오답 노트에서 읽기를 표시하는 색 코드


def load_questions(path):
    levels = [[], []]
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except FileNotFoundError:
        raise RuntimeError(f"{path} 파일을 찾을 수 없습니다. build.eds와 같은 폴더에 있어야 합니다.")
    except UnicodeDecodeError:
        raise RuntimeError(f"{path}: UTF-8 형식이 아닙니다. 엑셀에서는 'CSV UTF-8(쉼표로 분리)'로 저장해 주세요.")
    with io.StringIO(text, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # 제목 줄
        for line_no, row in enumerate(reader, start=2):
            cells = [cell.strip() for cell in row]
            if not any(cells) or cells[0].startswith("#"):
                continue
            where = f"{path} {line_no}번째 줄"
            if len(cells) < 8:
                raise RuntimeError(f"{where}: 칸이 8개 필요합니다. (난이도, 예문, 단어, 정답, 오답1, 오답2, 오답3, 뜻)")
            level_text, sentence, word, correct, wrong1, wrong2, wrong3, meaning = cells[:8]
            if level_text not in LEVEL_CODES:
                raise RuntimeError(f"{where}: 난이도는 '초급' 또는 '고급'이어야 합니다. (입력값: {level_text!r})")
            set_b = (cells[8:11] + ["", "", ""])[:3]
            for cell in cells[:8] + set_b:
                if any(ord(ch) < 32 for ch in cell):
                    raise RuntimeError(f"{where}: 칸 안에 줄바꿈이나 제어 문자가 있습니다.")
            if not sentence or not word or word not in sentence:
                raise RuntimeError(f"{where}: 단어({word!r})가 예문 안에 그대로 들어 있어야 합니다.")
            choices = [correct, wrong1, wrong2, wrong3]
            if "" in choices or len(set(choices)) != 4:
                raise RuntimeError(f"{where}: 정답과 오답 3개는 비어 있거나 서로 같으면 안 됩니다.")
            if any(set_b):
                if "" in set_b:
                    raise RuntimeError(f"{where}: 오답4~6(세트 B)은 3칸 모두 채우거나 3칸 모두 비워야 합니다. (9~11번째 칸에 메모를 적지 마세요. 메모는 12번째 칸부터입니다.)")
                choices_b = [correct] + set_b
                if len(set(choices_b)) != 4:
                    raise RuntimeError(f"{where}: 세트 B의 정답과 오답 3개는 서로 같으면 안 됩니다.")
            else:
                choices_b = choices   # 세트 B가 없으면 세트 A를 그대로 씁니다.
            if not meaning:
                raise RuntimeError(f"{where}: 뜻이 비어 있습니다.")
            if len(sentence) > MAX_SENTENCE_LENGTH:
                print(f"[경고] {where}: 예문이 {len(sentence)}글자로 깁니다. 화면에 안 맞을 수 있어요.")
            set_text = cells[14] if len(cells) > 14 else ""
            if not set_text.isdigit() or int(set_text) < 1:
                raise RuntimeError(f"{where}: 15번째 칸(세트)에 1 이상의 세트 번호를 적어 주세요. (입력값: {set_text!r})")
            levels[LEVEL_CODES[level_text]].append({
                "set": int(set_text),
                "sentence": sentence.replace(word, HIGHLIGHT_ON + word + HIGHLIGHT_OFF, 1),
                "choices": choices,   # 세트 A. 정답이 항상 첫 번째
                "choices_b": choices_b,   # 세트 B. 정답이 항상 첫 번째
                "meaning": f"{HIGHLIGHT_ON}{word}{HIGHLIGHT_OFF} = {meaning}",
                "note": f"{HIGHLIGHT_ON}{word}{HIGHLIGHT_OFF} {NOTE_READING_COLOR}[{correct}]{HIGHLIGHT_OFF} = {meaning}",   # 오답 노트 한 줄: 한자 [읽기] = 뜻
            })
    for code, label in enumerate(LEVEL_LABELS):
        if not levels[code]:
            raise RuntimeError(f"{path}: {label} 문제가 하나도 없습니다. 난이도마다 최소 1문제는 필요합니다.")
    return levels


_question_levels = load_questions(QUESTION_FILE)
# 난이도(초급 → 고급) 순서로, 같은 난이도 안에서는 세트 번호 순서로 문제를 정렬합니다. (같은 세트는 연속으로 놓입니다.)
_question_levels = [sorted(level, key=lambda q: q["set"]) for level in _question_levels]
_questions = _question_levels[0] + _question_levels[1]

QuestionSentences = EUDArray([Db(q["sentence"]) for q in _questions])
QuestionChoices = EUDArray([Db(choice) for q in _questions for choice in q["choices"] + q["choices_b"]])   # 문제당 8개: 세트 A 4개 + 세트 B 4개 (각 세트의 첫 번째가 정답)
QuestionMeanings = EUDArray([Db(q["meaning"]) for q in _questions])
QuestionNotes = EUDArray([Db(q["note"]) for q in _questions])   # 단어장용 "한자 [읽기] = 뜻"
QuestionLevels = EUDArray([0] * len(_question_levels[0]) + [1] * len(_question_levels[1]))   # 문제별 난이도 (0: 초급, 1: 고급)
MaxLevelCount = len(_questions)

# 세트 번호는 1 ~ SetCount. 게임 안에서 세트 0은 "전체 세트"를 뜻합니다.
SetCount = max(q["set"] for q in _questions)
SetStride = SetCount + 1
# 난이도(0: 초급, 1: 고급)와 세트 번호(0: 전체)에 해당하는 문제는 항상 연속된 한 구간입니다.
# 구간 번호 = 난이도 * SetStride + 세트 번호
_pool_first, _pool_count = [], []
_offset = 0
for _level in _question_levels:
    _first_of_level = _offset
    _pool_first.append(_first_of_level)
    _pool_count.append(len(_level))
    for _set_no in range(1, SetCount + 1):
        _members = [k for k, q in enumerate(_level) if q["set"] == _set_no]
        _pool_first.append(_first_of_level + (_members[0] if _members else 0))
        _pool_count.append(len(_members))
    _offset += len(_level)
PoolFirst = EUDArray(_pool_first)
PoolCount = EUDArray(_pool_count)
print(f"[문제 데이터] 초급 {len(_question_levels[0])}문제, 고급 {len(_question_levels[1])}문제, 세트 {SetCount}개를 불러왔습니다.")

init()
