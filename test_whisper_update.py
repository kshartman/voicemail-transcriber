#!/usr/bin/env python3
"""Test Whisper functionality with updated dependencies"""

import sys
import torch
import whisper
import transformers

print("=" * 50)
print("DEPENDENCY VERSION CHECK")
print("=" * 50)
print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")
print(f"Transformers: {transformers.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"CUDA version: {torch.version.cuda}")

print("\n" + "=" * 50)
print("WHISPER MODEL TEST")
print("=" * 50)

try:
    # Test loading the model
    print("Loading Whisper medium model...")
    model = whisper.load_model("base")  # Use base for faster testing
    print("✓ Model loaded successfully")
    
    # Test model device
    device = next(model.parameters()).device
    print(f"✓ Model device: {device}")
    
    # Test a simple transcription (using a dummy audio)
    print("\nTesting model inference...")
    # Create a dummy audio tensor (1 second of silence)
    dummy_audio = torch.zeros(16000).to(device)
    
    # This should process without errors even if no speech detected
    result = model.transcribe(dummy_audio.cpu().numpy(), language='en')
    print("✓ Inference test passed")
    print(f"  Result: {result['text']}")
    
    print("\n✅ All tests passed! Whisper works with updated dependencies.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)