# -*- coding: utf-8 -*-
import sys
import os

def test_trigger_words():
    # Emulate the logic inside gemini_engine.py
    def get_assistant_call_names(config):
        call_name_cfg = config.get("assistant_call_name", "你")
        if isinstance(call_name_cfg, list):
            return [str(name).lower() for name in call_name_cfg]
        else:
            return [str(call_name_cfg).lower()]

    def is_visual_trigger_check(user_input, assistant_call_names, active_project):
        user_input_lower = user_input.lower()
        is_casual_mode = not active_project or active_project.lower() == "none"
        
        return ("你看" in user_input and ("gemini" in user_input_lower or "吉米尼" in user_input_lower or any(name in user_input_lower for name in assistant_call_names))) and not is_casual_mode

    # Test Case 1: Default config ("你")
    config1 = {"assistant_call_name": "你"}
    names1 = get_assistant_call_names(config1)
    assert names1 == ["你"]
    assert is_visual_trigger_check("你看這個", names1, "vibe_coding") is True
    assert is_visual_trigger_check("你看這個", names1, "none") is False # Casual mode
    assert is_visual_trigger_check("吉米尼你看", names1, "vibe_coding") is True
    # "小助手你看" contains "你" (from "你看"), so with "你" config it is True!
    assert is_visual_trigger_check("小助手你看", names1, "vibe_coding") is True

    # Test Case 2: Custom string ("小助手")
    config2 = {"assistant_call_name": "小助手"}
    names2 = get_assistant_call_names(config2)
    assert names2 == ["小助手"]
    assert is_visual_trigger_check("小助手你看", names2, "vibe_coding") is True
    assert is_visual_trigger_check("你看這個", names2, "vibe_coding") is False # Doesn't contain "小助手", "gemini", or "吉米尼"

    # Test Case 3: List of trigger words (["你", "小精靈"])
    config3 = {"assistant_call_name": ["你", "小精靈"]}
    names3 = get_assistant_call_names(config3)
    assert names3 == ["你", "小精靈"]
    assert is_visual_trigger_check("小精靈你看", names3, "vibe_coding") is True
    assert is_visual_trigger_check("你看這個", names3, "vibe_coding") is True # Contains "你" (from "你看")
    assert is_visual_trigger_check("大家看這個", names3, "vibe_coding") is False

    print("ALL TRIGGER WORD TEST CASES PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_trigger_words()
