"""Download and quantize T5 model weights for witchcraft.

Requires: pip install transformers torch safetensors

Usage: python downloadweights.py --output-dir ./assets
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import safetensors.torch
import torch
from huggingface_hub import snapshot_download
from transformers import T5EncoderModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    args = parser.parse_args()

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    print("Downloading google/xtr-base-en from Hugging Face...")
    model_dir = snapshot_download(
        "google/xtr-base-en",
        local_dir=str(output / "_hf_model"),
    )

    print("Loading encoder model...")
    model = T5EncoderModel.from_pretrained(model_dir)

    # Extract encoder weights + linear projection
    state_dict = model.state_dict()

    # Load the dense projection layer (768 -> 128)
    dense_path = Path(model_dir) / "2_Dense" / "pytorch_model.bin"
    if dense_path.exists():
        dense = torch.load(dense_path, map_location="cpu", weights_only=True)
        state_dict["linear.weight"] = dense["linear.weight"].to(torch.float16)

    # Convert all to float16
    tensors = {}
    for k, v in state_dict.items():
        tensors[k] = v.to(torch.float16)

    safetensors_path = output / "xtr.safetensors"
    print(f"Saving {len(tensors)} tensors to {safetensors_path}...")
    safetensors.torch.save_file(tensors, str(safetensors_path))

    # Copy config and tokenizer
    import shutil

    for name in ("config.json", "tokenizer.json"):
        src = Path(model_dir) / name
        if src.exists():
            shutil.copy2(src, output / name)

    # Clean up downloaded model
    shutil.rmtree(output / "_hf_model", ignore_errors=True)

    print(f"Done. Assets in {output}/")
    print("Note: run quantize-tool to convert xtr.safetensors -> xtr.gguf")


if __name__ == "__main__":
    main()
