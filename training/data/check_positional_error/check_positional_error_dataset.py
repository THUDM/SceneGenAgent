# Copyright (c) Meta Platforms, Inc. and affiliates.
# This software may be used and distributed according to the terms of the Llama 2 Community License Agreement.

# For dataset details visit: https://huggingface.co/datasets/samsum

import copy
import datasets
import itertools



def tokenize_dialog(dialog, tokenizer):
    dialog_tokens = tokenizer.apply_chat_template(dialog)
    eot_indices = [i for i,n in enumerate(dialog_tokens) if n == tokenizer.eos_token_id]
    labels = copy.copy(dialog_tokens)
    last_idx = 0
    for n, idx in enumerate(eot_indices):
        if n % 2 == 1:
            last_idx = idx
        else:
            labels[last_idx:idx+1] = [-100] * (idx-last_idx+1)

    dialog_tokens = [dialog_tokens]
    labels_tokens = [labels]

    combined_tokens = {
        "input_ids": list(itertools.chain(*(t for t in dialog_tokens))),
        "labels": list(itertools.chain(*(t for t in labels_tokens))),
    }

    return dict(combined_tokens, attention_mask=[1]*len(combined_tokens["input_ids"]))

def get_custom_dataset(dataset_config, tokenizer, split):
    dataset = datasets.load_dataset('json', data_files={
        'train': [
            '<train jsonl path>', # Fill
        ],
        'test': [
            '<test jsonl path>', # Fill
        ]
    }, split=split)

    dataset = dataset.map(lambda sample: {
        "id": sample["id"],
        "list_positions_id": sample["list_positions_id"],
        "conversation": [
            {'role': 'user', 'content': sample['model_input']},
            {'role': 'assistant', 'content': sample['model_output']}
        ],
        },
        remove_columns=list(dataset.features),)

    dataset = dataset.map(lambda x: tokenize_dialog(x["conversation"], tokenizer), remove_columns=list(dataset.features))

    return dataset
