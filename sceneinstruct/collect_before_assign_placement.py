import os
import json
import pandas as pd
from multiprocessing import Process
from tqdm import tqdm
from argparse import ArgumentParser
from layout_analysis import retrieve_objects, extract_layout
from model import LocalModel

def worker(id, data, input_path):
    model_local = LocalModel('<model-checkpoint-path>')
    output_path_retrieve_objects = input_path.replace('.jsonl', '_retrieve_objects.jsonl')
    output_path_extract_layout = input_path.replace('.jsonl', '_extract_layout.jsonl')
    with open(output_path_retrieve_objects.replace('.json', f'_{id}.json'), 'w', encoding='utf-8') as f_retrieve_objects, \
         open(output_path_extract_layout.replace('.json', f'_{id}.json'), 'w', encoding='utf-8') as f_extract_layout:
        for d in tqdm(data):
            objects, rewritten_prompt, analysis_list_objects, model_input_retrieve_objects, model_output_retrieve_objects = retrieve_objects(d['description'], model_local)
            d_retrieve_objects = {
                'id': d['id'],
                'description_id': d['id'],
                'model_input': model_input_retrieve_objects,
                'model_output': model_output_retrieve_objects,
                'objects': objects,
                'rewritten_prompt': rewritten_prompt,
            }
            f_retrieve_objects.write(json.dumps(d_retrieve_objects, ensure_ascii=False) + '\n')
            f_retrieve_objects.flush()
            model_output_extract_layout, objects, coordinates, relations, analysis_extract_layout, model_input_extract_layout = extract_layout(rewritten_prompt, objects, model_local)
            d_extract_layout = {
                'id': d_retrieve_objects['id'],
                'retrieve_objects_id': d_retrieve_objects['id'],
                'model_input': model_input_extract_layout,
                'model_output': model_output_extract_layout,
                'prompt': rewritten_prompt,
                'objects': objects,
                'coordinates': coordinates,
                'relations': relations,
            }
            f_extract_layout.write(json.dumps(d_extract_layout, ensure_ascii=False) + '\n')
            f_extract_layout.flush()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("--input-path", type=str, default="data_prompt.jsonl")

    args = parser.parse_args()
    data = list(map(json.loads, open(args.input_path, encoding='utf-8').readlines()))

    num_workers = 10

    k, m = divmod(len(data), num_workers)
    data_workers = [data[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(num_workers)]

    processes = []
    for i in range(num_workers):
        p = Process(target=worker, args=(i, data_workers[i], args.input_path))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    for suffix in ['retrieve_objects', 'extract_layout']:
        results = [i for j in [list(map(json.loads, open(args.input_path.replace('.jsonl', f'_{suffix}.jsonl').replace('.json', f'_{k}.json'), encoding='utf-8').readlines())) for k in range(num_workers)] for i in j]
        results = sorted(results, key=lambda x: x['id'])
        with open(args.input_path.replace('.jsonl', f'_{suffix}.jsonl'), 'w', encoding='utf-8') as f:
            for d in results:
                f.write(json.dumps(d, ensure_ascii=False) + '\n')
        for i in range(num_workers):
            if os.path.exists(args.input_path.replace('.jsonl', f'_{suffix}.jsonl').replace('.json', f'_{i}.json')):
                os.remove(args.input_path.replace('.jsonl', f'_{suffix}.jsonl').replace('.json', f'_{i}.json'))
