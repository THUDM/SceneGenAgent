output_dir=output
mkdir -p $output_dir

python eval.py \
    --prompts benchmark/test_data.csv \
    --output-path $output_dir/generation.jsonl
