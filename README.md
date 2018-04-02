# How to start
first, you need to have python 3 installed along with [Tensorflow v1.6](https://www.tensorflow.org/install/).

next you can install the requirements using:

> pip install -r requirements.txt

# Basic Dataset:
We tested the code above on the [ljspeech dataset](https://keithito.com/LJ-Speech-Dataset/), which has almost 24 hours of labeled single actress voice recording. (further info on the dataset are available in the README file when you download it)

After **downloading** the dataset, **extract** the compressed file, and **place the folder inside the cloned repository.**

# Preprocessing

From this point and further, you'll have to be located inside the "tacotron" folder

> cd tacotron

Preprocessing can then be started using: 

> python preprocess.py

This should take **few minutes.**

# Training:
Feature prediction model can be **trained** using:

> python train.py

checkpoints will be made each **100 steps** and stored under **logs-<model_name> folder.**

# Synthesis
There are **three types** of mel spectrograms synthesis using this model:

- **Evaluation** (synthesis on custom sentences). This is what we'll usually use after having a full end to end model.

> python synthesize.py --mode='eval'

- **Natural synthesis** (let the model make predictions alone by feeding last decoder output to the next time step).

> python synthesize.py --GTA=False

- **Ground Truth Aligned synthesis** (DEFAULT: the model is assisted by true labels in a teacher forcing manner). This synthesis method is used when predicting mel spectrograms used to train the wavenet vocoder. (yields better results as stated in the paper)

> python synthesize.py


# References:
 https://github.com/Rayhane-mamah/Tacotron-2
