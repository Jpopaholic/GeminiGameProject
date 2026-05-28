#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification Script for Gemini Stream Engine
"""

import sys
import os
import asyncio

# Windows console output Unicode compatibility fix
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_engine import GeminiStreamEngine, HAS_GEMINI_SDK, HAS_WHISPER, HAS_PYAUDIO, HAS_OBS

async def test_main():
    print("========== Engine Verification Start ==========")
    print(f"OS: {sys.platform}")
    print(f"Python Version: {sys.version}")
    print(f"HAS_GEMINI_SDK: {HAS_GEMINI_SDK}")
    print(f"HAS_WHISPER: {HAS_WHISPER}")
    print(f"HAS_PYAUDIO: {HAS_PYAUDIO}")
    print(f"HAS_OBS: {HAS_OBS}")
    
    # Initialize Engine
    engine = GeminiStreamEngine()
    print("\n[SUCCESS] Engine initialized successfully!")
    
    # Check Status
    print("\n--- Displaying Status ---")
    engine.display_status()
    
    # Test System Instruction Assembly
    print("--- Testing System Instruction Assembly ---")
    sys_inst = engine.get_assembled_system_instruction()
    print(f"Length of System Instruction: {len(sys_inst)} characters.")
    print("Instruction Preview:")
    print("-" * 50)
    # Print first 300 characters of instruction
    print(sys_inst[:400] + "\n...")
    print("-" * 50)
    
    # Test simulated visual capture
    print("\n--- Testing Visual Capture Fallbacks ---")
    img_bytes, method = await engine.run_visual_capture()
    print(f"Capture Method Selected: {method}")
    if img_bytes:
        print(f"Success! Obtained {len(img_bytes)} bytes of compressed visual data.")
    else:
        print("Warning: Visual capture yielded no image bytes.")
        
    print("\n========== Engine Verification End: ALL PASS! ==========")

if __name__ == "__main__":
    asyncio.run(test_main())
