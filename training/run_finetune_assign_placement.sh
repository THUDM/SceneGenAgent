TIMESTAMP=$(date +'%Y.%m.%d-%H:%M:%S')
mkdir -p logs

LR=${1:-1e-4}
lora_r=${2:-64}
lora_alpha=${3:-128}
batch_size=${4:-2}
gradient_accumulation_steps=${5:-16}

EXPNAME=assign_placement-lr${LR}-lora_r${lora_r}-lora_alpha${lora_alpha}-bs${batch_size}-accum${gradient_accumulation_steps}-${TIMESTAMP}
MODEL_PATH=<model-checkpoint-path> # Fill
ARGS="finetuning.py \
    --enable_fsdp \
    --model_name $MODEL_PATH \
    --output_dir models/assign_placement/$EXPNAME \
    --dataset custom_dataset \
    --file data/assign_placement/assign_placement_dataset.py \
    --train_split train \
    --test_split test \
    --use_peft \
    --peft_method lora \
    --lora_r $lora_r \
    --lora_alpha $lora_alpha \
    --lora_target_modules q_proj,k_proj,v_proj,o_proj \
    --batch_size_training $batch_size \
    --gradient_accumulation_steps $gradient_accumulation_steps \
    --lr $LR \
    --num_epochs 8 \
    --save_metrics"

run_cmd="torchrun --nnodes 1 --nproc_per_node 8 $ARGS"
echo $run_cmd
LOG_PATH=logs/${EXPNAME}
mkdir -p $LOG_PATH
eval ${run_cmd} 2>&1 | tee ${LOG_PATH}/output.log