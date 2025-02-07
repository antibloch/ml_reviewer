#!/bin/bash

# Activate the Conda environment
source ~/anaconda3/etc/profile.d/conda.sh  # Adjust path to appropiate environment

conda create -n pytorch python=3.10 -y && conda activate pytorch

pip install torch==2.0.0+cu118 torchvision==0.15.1+cu118 torchaudio==2.0.1+cu118 --index-url https://download.pytorch.org/whl/cu118

pip install scikit-learn

conda install scikit-image -y

pip install matplotlib

pip install ultralytics

pip install transformers accelerate

pip install colour

pip install rich

pip install timm opacus

pip install smolagents

pip install markdownify markdown weasyprint

