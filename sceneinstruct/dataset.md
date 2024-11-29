# Build SceneInstruct Dataset

Please follow the instructions below to reproduce the procedure of building SceneInstruct.

## Model Preparation

- **Llama-3.1-70B-Instruct**: You can download the weights of Llama-3.1-70B-Instruct at [HF Repo](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct). To serve Llama-3.1-70B-Instruct with vLLM:
  ```shell
  vllm serve <Llama-3.1-70B path> --tensor_parallel_size 2
  ```
- **OpenAI API key**: Create a file `openai_key` and add your API key.

## Create Scene Descriptions with Evol-Instruct

1. Deploy Llama-3.1-70B-Instruct following [Model Preparation](#model-preparation).
2. Set `<model-checkpoint-path>` in [create_descriptions.py](create_descriptions.py#L50) to your model path.
3. Run the following command:
   ```shell
   python create_descriptions.py \
       --num-prompts-needed 3000 # the number of new descriptions to be created
   ```
4. The generated descriptions are saved in `data_prompt.jsonl` by default.

## Collect SceneGenAgent Trajectories

1. Deploy the models following [Model Preparation](#model-preparation).
2. Set `<model-checkpoint-path>` in [create_descriptions.py](create_descriptions.py#L50) to your model path.
3. Run the following command:
   ```shell
   python collect_before_assign_placement.py
   python collect_assign_placement.py
   ```
4. The generated SceneInstruct dataset is saved in three files: `data_prompt_assign_placement.jsonl`, `data_prompt_check_positional_error.jsonl`, and `data_prompt_fix_positional_error.jsonl`.
