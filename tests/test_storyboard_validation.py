from app.schemas.storyboard import (
    Scene,
    ShotScript,
    StoryboardTemplate,
    validate_scenes_list,
    validate_storyboard_template,
)


def test_validate_storyboard_rejects_empty_shots() -> None:
    t = StoryboardTemplate(shots=[])
    errs = validate_storyboard_template(t)
    assert errs and "shots 不能为空" in errs[0]


def test_validate_storyboard_timeline() -> None:
    t = StoryboardTemplate(
        shots=[
            ShotScript(id="S01", start_s=0.0, end_s=2.0),
            ShotScript(id="S02", start_s=1.0, end_s=4.0),
        ]
    )
    errs = validate_storyboard_template(t)
    assert any("不得早于" in e for e in errs)


def test_validate_storyboard_ok_contiguous() -> None:
    t = StoryboardTemplate(
        shots=[
            ShotScript(id="S01", start_s=0.0, end_s=2.0),
            ShotScript(id="S02", start_s=2.0, end_s=5.0),
        ]
    )
    assert validate_storyboard_template(t) == []


def test_validate_scenes_rejects_empty() -> None:
    errs = validate_scenes_list([])
    assert errs and "不能为空" in errs[0]


def test_validate_scenes_duplicate_id() -> None:
    scenes = [
        Scene(id="S01", duration_sec=1.0),
        Scene(id="S01", duration_sec=1.0),
    ]
    errs = validate_scenes_list(scenes)
    assert any("重复" in e for e in errs)


def test_validate_scenes_non_positive_duration() -> None:
    scenes = [Scene(id="S01", duration_sec=0.0)]
    errs = validate_scenes_list(scenes)
    assert any("duration_sec" in e for e in errs)
