import os
import json
from multiprocessing import Process, Value
from tqdm import tqdm
from argparse import ArgumentParser
from layout_analysis import assign_placement
from model import ChatGPT

def worker(id, data, input_path, max_id_assign_placement, max_id_check_positional_error, max_id_fix_positional_error):
    model = ChatGPT()
    output_path_assign_placement = input_path.replace('.jsonl', '_assign_placement.jsonl')
    output_path_check_positional_error = input_path.replace('.jsonl', '_check_positional_error.jsonl')
    output_path_fix_positional_error = input_path.replace('.jsonl', '_fix_positional_error.jsonl')
    with open(output_path_assign_placement.replace('.json', f'_{id}.json'), 'w', encoding='utf-8') as f_assign_placement, \
         open(output_path_check_positional_error.replace('.json', f'_{id}.json'), 'w', encoding='utf-8') as f_check_positional_error, \
         open(output_path_fix_positional_error.replace('.json', f'_{id}.json'), 'w', encoding='utf-8') as f_fix_positional_error:
        for d in tqdm(data):
            coords_final, model_output_assign_placement, analysis, failed_rounds, model_input_assign_placement, positional_error_list, fix_error_list = assign_placement(d['prompt'], d['objects'], d['coordinates'], d['relations'], model)
            with max_id_assign_placement.get_lock():
                max_id_assign_placement.value += 1
                d_assign_placement = {
                    'id': max_id_assign_placement.value,
                    'extract_layout_id': d['id'],
                    'model_input': model_input_assign_placement,
                    'model_output': model_output_assign_placement,
                    'coords_final': coords_final,
                }
            f_assign_placement.write(json.dumps(d_assign_placement, ensure_ascii=False) + '\n')
            f_assign_placement.flush()

            for positional_error in positional_error_list:
                with max_id_check_positional_error.get_lock():
                    max_id_check_positional_error.value += 1
                    d_positional_error = {
                        'id': max_id_check_positional_error.value,
                        'extract_layout_id': d['id'],
                        **positional_error,
                    }
                f_check_positional_error.write(json.dumps(d_positional_error, ensure_ascii=False) + '\n')
                f_check_positional_error.flush()
            
            for fix_error in fix_error_list:
                with max_id_fix_positional_error.get_lock():
                    max_id_fix_positional_error.value += 1
                    d_fix_error = {
                        'id': max_id_fix_positional_error.value,
                        'extract_layout_id': d['id'],
                        **fix_error,
                    }
                f_fix_positional_error.write(json.dumps(d_fix_error, ensure_ascii=False) + '\n')
                f_fix_positional_error.flush()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("--input-path", type=str, default="data_prompt_extract_layout.jsonl")
    parser.add_argument("--save-prefix", type=str, default="data_prompt")

    args = parser.parse_args()
    data = list(map(json.loads, open(args.input_path, encoding='utf-8').readlines()))
    output_path = f"{args.save_prefix}.jsonl"

    num_workers = 10

    k, m = divmod(len(data), num_workers)
    data_workers = [data[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(num_workers)]

    max_id_assign_placement = Value('i', 0)
    max_id_check_positional_error = Value('i', 0)
    max_id_fix_positional_error = Value('i', 0)
    processes = []
    for i in range(num_workers):
        p = Process(target=worker, args=(i, data_workers[i], output_path, max_id_assign_placement, max_id_check_positional_error, max_id_fix_positional_error))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    for suffix in ['assign_placement', 'check_positional_error', 'fix_positional_error']:
        results = [i for j in [list(map(json.loads, open(output_path.replace('.jsonl', f'_{suffix}.jsonl').replace('.json', f'_{k}.json'), encoding='utf-8').readlines())) for k in range(num_workers)] for i in j]
        results = sorted(results, key=lambda x: x['id'])
        with open(output_path.replace('.jsonl', f'_{suffix}.jsonl'), 'w', encoding='utf-8') as f:
            for d in results:
                f.write(json.dumps(d, ensure_ascii=False) + '\n')
        for i in range(num_workers):
            if os.path.exists(output_path.replace('.jsonl', f'_{suffix}.jsonl').replace('.json', f'_{i}.json')):
                os.remove(output_path.replace('.jsonl', f'_{suffix}.jsonl').replace('.json', f'_{i}.json'))
