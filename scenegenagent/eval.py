import os
import json
import pandas as pd
from multiprocessing import Process
from tqdm import tqdm
from argparse import ArgumentParser
from layout_analysis import process_prompt
from code_gen import gen_code, show_complete_code
from model import GPT4O, LocalModel

model_dict = {
    'default': LocalModel('<model-checkpoint-path>', base_url='http://localhost:8000/v1'),
    'retrieve_objects': None,
    'extract_layout': None,
    'assign_placement': LocalModel('assign_placement', base_url='http://localhost:8000/v1'),
    'check_positional_error': LocalModel('check_positional_error', base_url='http://localhost:8000/v1'),
    'fix_positional_error': LocalModel('fix_positional_error', base_url='http://localhost:8000/v1'),
    'generate_code': None,
    'fix_code': None
}
assert model_dict['default'] is not None
model_default = model_dict['default']
model_dict = {k: v if v else model_default for k, v in model_dict.items()}

def generate(text):
    objects, placement, rewritten_prompt, _, _ = process_prompt(text,
        model_retrieve_objects=model_dict.get('retrieve_objects', model_default),
        model_extract_layout=model_dict.get('extract_layout', model_default),
        model_assign_placement=model_dict.get('assign_placement', model_default),
        model_check_positional_error=model_dict.get('check_positional_error', model_default),
        model_fix_positional_error=model_dict.get('fix_positional_error', model_default)
    )
    code, _ = gen_code(rewritten_prompt, objects, placement,
        model=model_default,
        model_generate_code=model_dict.get('generate_code', model_default),
        model_fix_code=model_dict.get('fix_code', model_default)
    )
    code = show_complete_code(code)
    return code

def worker(id, data, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i in tqdm(range(len(data))):
            code = generate(data[i]['description'])
            data[i]['code'] = code
            f.write(json.dumps(data[i], ensure_ascii=False) + '\n')
            f.flush()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--prompts', type=str, default='benchmark/test_data.csv')
    parser.add_argument('--output-path', type=str, required=True)
    args = parser.parse_args()
    data = pd.read_csv(args.prompts)
    data = [dict(i[1]) for i in data.iterrows()]
    data = [{k: d[k] for k in ['id', 'description']} for d in data]
    os.makedirs(os.path.split(args.output_path)[0], exist_ok=True)

    num_workers = 8

    k, m = divmod(len(data), num_workers)
    data_workers = [data[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(num_workers)]

    processes = []
    for i in range(num_workers):
        p = Process(target=worker, args=(i, data_workers[i], args.output_path.replace('.json', f'_{i}.json')))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

    results = [i for j in [list(map(json.loads, open(args.output_path.replace('.json', f'_{k}.json'), encoding='utf-8').readlines())) for k in range(num_workers)] for i in j]
    results = sorted(results, key=lambda x: x['id'])
    with open(args.output_path, 'w', encoding='utf-8') as f:
        for d in results:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')
    for i in range(num_workers):
        if os.path.exists(args.output_path.replace('.json', f'_{i}.json')):
            os.remove(args.output_path.replace('.json', f'_{i}.json'))
