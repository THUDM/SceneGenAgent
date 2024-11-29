import json
import numpy as np
from tqdm import tqdm
from termcolor import colored
from argparse import ArgumentParser
from dataclasses import asdict

from model import LocalModel
from cleaning import filter_prompt, clean_prompt_model
from prompts import InstructionWithMeta, evol_base_prompt, evol_feedback_prompt, get_evol_input
from minhash import Hash

def gen_prompt_with_retry(model_input: str, model, method: str, evol_feedback_prompt: str, hash: Hash, retries=3):
    prompt_new = None
    messages = [{
        "role": "user",
        "content": model_input
    }]
    for retry in range(retries):
        try:
            model_output = model.invoke(messages).strip()
            assert model_output
            model_output = clean_prompt_model(model_output, model)
            should_filter, filter_reason = filter_prompt(model_output, model)
            if not should_filter and not hash.can_insert(model_output):
                should_filter = True
                filter_reason = "Similar descriptions already exist. Try to change in other ways."
            if should_filter:
                print(colored(f"Retry: {retry}\nMethod: {method}\nPrompt: {json.dumps([model_input])}", 'red') + f"\nResponse: {[model_output]}" + f"\nFilter reason: {[filter_reason]}")
                messages.extend([
                    {"role": "assistant", "content": model_output},
                    {"role": "user", "content": evol_feedback_prompt.format(feedback=filter_reason)}
                ])
                continue
            prompt_new = model_output
            break
        except Exception as e:
            print(e)
            continue
    return prompt_new

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("--input-path", type=str, default="data/data_seed.jsonl")
    parser.add_argument("--output-path", type=str, default="data_prompt.jsonl")
    parser.add_argument("--id-start-from", type=int, default=1)
    parser.add_argument("--num-prompts-needed", type=int, default=3000)
    args = parser.parse_args()

    model = LocalModel('<model-checkpoint-path>')
    threshold = 0.8
    num_perm = 128
    hash = Hash(threshold=threshold, num_perm=num_perm)

    data = list(map(json.loads, open(args.input_path, encoding='utf-8').readlines()))
    data = sorted([InstructionWithMeta(**d) for d in data], key=lambda x: x.id)
    data = {d.id: d for d in data}
    max_id = max(data)
    if max_id < args.id_start_from - 1:
        max_id = args.id_start_from - 1
    for id, d in data.items():
        hash.insert(id, d.description, check=False)

    # add prompts
    num_prompts_needed = args.num_prompts_needed
    np.random.seed(42)

    with open(args.output_path, 'w', encoding='utf-8') as f:
        for d in sorted(list(data.values()), key=lambda x: x.id):
            f.write(json.dumps(asdict(d), ensure_ascii=False) + '\n')
        for i in tqdm(range(num_prompts_needed)):
            instruction_id = np.random.choice(list(data.keys()))
            instruction = data[instruction_id]
            
            evol_prompt, method, method_id = get_evol_input(instruction, evol_base_prompt)
            description_new = gen_prompt_with_retry(evol_prompt, model, method, evol_feedback_prompt, hash, retries=3)
            if not description_new:
                continue
            max_id += 1
            print(f"ID: {max_id}\nMethod: {method}\nOriginal description: {instruction.description}\nNew description: {description_new}\n")
            hash.insert(max_id, description_new)
            new_instruction = InstructionWithMeta(
                id=max_id,
                description=description_new,
                parent_id=instruction.id,
                augment_method=method,
                depth=instruction.depth + 1,
                has_quantity_changed=instruction.has_quantity_changed or (method_id == 3),
            )
            data[new_instruction.id] = new_instruction
            f.write(json.dumps(asdict(new_instruction), ensure_ascii=False) + '\n')
            f.flush()
