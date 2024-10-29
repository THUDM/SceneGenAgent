# Training with SceneInstruct

We currently support LoRA fine-tuning. Please follow the instructions below to fine-tuning models with SceneInstruct as the backbone of SceneGenAgent.

## Data Preparation
Download the data from [Tsinghua Cloud](https://cloud.tsinghua.edu.cn/d/19c1e04370174f95bf08/). The data covers three tasks in SceneGenAgent: assign placement, check positional error, and fix positional error.

## Fine-tuning
Take `assign_placement` as an example:

### Preparation

1. Change the JSONL data paths of `get_custom_dataset` method in [assign_placement_dataset.py](data/assign_placement/assign_placement_dataset.py#L35) to your own data paths
2. Change the `MODEL_PATH` argument in [run_finetune_assign_placement.sh](run_finetune_assign_placement.sh#L11) to your model path. You may also adjust the training hyper-parameters in this shell script.
3. If necessary, re-implement how `labels_tokens` is obtained in the `tokenize_dialog` method of [assign_placement_dataset.py](data/assign_placement/assign_placement_dataset.py#L24). This is to make sure the loss is computed only using the output in the final rounds of the conversational data. The current implementation is for the Llama-3 series, but may not suit other models.

### Run training
To train the model, run:
```shell
bash run_finetune_assign_placement.sh
```
