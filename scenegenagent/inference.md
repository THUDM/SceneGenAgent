# SceneGenAgent

Please follow the instructions below to run the SceneGenAgent inference with offline or API-based models.

## Model Deployment

### Offline Models

We take our LoRA fine-tuned Llama-3.1-70B-Instruct as an example. Here is the full list of LoRA modules for Llama-3.1-70B-Instruct we released:

| Name | HF Repo |
|---|---|
| SceneGenAgent-Llama-3.1-70B-assign-placement  | [🤗 HF Repo](https://huggingface.co/Rishubi/SceneGenAgent-Llama-3.1-70B-assign-placement) |
| SceneGenAgent-Llama-3.1-70B-check-positional-error | [🤗 HF Repo](https://huggingface.co/Rishubi/SceneGenAgent-Llama-3.1-70B-check-positional-error) |
| SceneGenAgent-Llama-3.1-70B-fix-positional-error | [🤗 HF Repo](https://huggingface.co/Rishubi/SceneGenAgent-Llama-3.1-70B-fix-positional-error) |

You can download the weights of Llama-3.1-70B-Instruct at [HF Repo](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct).

The models should be served with OpenAI-compatible servers. For example, to serve Llama-3.1-70B along with multiple LoRA adapters with vLLM:
```shell
vllm serve <Llama-3.1-70B path> --tensor_parallel_size 2 --enable-lora --lora-modules assign_placement=<assign placement lora path> check_positional_error=<check positional error lora path> fix_positional_error=<fix positional error lora path> --max-lora-rank 64
```

Note that serving Llama-3.1-70B with LoRA adapters takes approximately 160GB of GPU memory.

### API-based Models

For OpenAI models, we have implemented `GPT4O` in [model.py](model.py#L84) which supports other models as well should you change its `model_name`. if you use our `GPT4O` implementation, you should create a file `openai_key` and add your API key.

For models incompatible with OpenAI API, you should create a child class of `Model` in [model.py](model.py#L15) and implement its [generate](model.py#L49) and [invoke](model.py#L64) methods. `generate` accepts a single string as the `prompt` argument and `invoke` accepts multiple rounds of conversation as the `messages` argument.

## Run SceneGenAgent Gradio Demo

1. Deploy the models following [Model Deployment](#model-deployment).
2. Set the models you want to use in each part of SceneGenAgent in [demo.py](demo.py#L8). We have implemented `LocalModel` for you in [model.py](model.py#L80), and you may change `model_name` and `base_url` of `LocalModel`, set the models as `GPT4O` to serve API models, or use any self-implemented model objects. Setting a model to `None` causes this part of SceneGenAgent to use the default model.
3. Run the demo with the following command:
   ```shell
   python demo.py
   ```

## Run Evaluation on Benchmark

1. Deploy the models following [Model Deployment](#model-deployment).
2. Extract benchmark data with:
   ```shell
   cd benchmark
   tar -xzvf test_data.csv.tar.gz
   cd ..
   ```
3. Set the models you want to use in each part of SceneGenAgent in [eval.py](eval.py#L11). We have implemented `LocalModel` for you in [model.py](model.py#L80), and you may change `model_name` and `base_url` of `LocalModel`, set the models as `GPT4O` to serve API models, or use any self-implemented model objects. Setting a model to `None` causes this part of SceneGenAgent to use the default model.
4. Run evaluation with the following command:
   ```shell
   bash eval.sh
   ```
   The generated code is stored in `output/generation.jsonl` by default. To render the scene, run the code for each description in [Process Simulate](https://plm.sw.siemens.com/en-US/tecnomatix/products/process-simulate-software/).
