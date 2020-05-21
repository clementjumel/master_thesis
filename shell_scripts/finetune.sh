#!/bin/bash
#SBATCH --job-name=finetune
#SBATCH --partition=main
#SBATCH --gres=gpu:1
#SBATCH --mem-per-gpu=32G
#SBATCH --time=24:00:00
#SBATCH --error=/network/tmp1/jumelcle/logs/finetune-%j.err
#SBATCH --output=/network/tmp1/jumelcle/logs/finetune-%j.out

# Parameters
TASK_TYPE=$1
EXPERIMENT=$2
TASK=context-dependent-same-type
TRAIN_PROPORTION=50
VALID_PROPORTION=25
TEST_PROPORTION=25
RANKING_SIZE=24
BATCH_SIZE=4
CONTEXT_FORMAT=v0
TARGETS_FORMAT=v0
BART=bart.large.cnn

# Paths
MASTER_THESIS_PATH=/network/home/jumelcle/master_thesis
PREPROCESSED_DATA_PATH=/network/tmp1/jumelcle/results/preprocessed_data
PRETRAINED_MODELS_PATH=/network/tmp1/jumelcle/pretrained_models
CHECKPOINTS_PATH=/network/tmp1/jumelcle/results/checkpoints

# Recover full paths/names
FULL_TASK="$TASK"_"$TRAIN_PROPORTION"-"$VALID_PROPORTION"-"$TEST_PROPORTION"_rs"$RANKING_SIZE"_bs"$BATCH_SIZE"_cf-"$CONTEXT_FORMAT"_tf-"$TARGETS_FORMAT"
RESULTS_PATH="$CHECKPOINTS_PATH/$TASK_TYPE/$FULL_TASK/$EXPERIMENT"

# Print the parameters
echo "Parameters:"; echo $TASK_TYPE $TASK $EXPERIMENT; echo
echo "Results path:"; echo $RESULTS_PATH; echo

# Load miniconda
module load miniconda
source activate base
source activate nlp

# Load pretrained BART
tar -xf "$PRETRAINED_MODELS_PATH/$BART.tar.gz" -C $SLURM_TMPDIR

# Load the preprocessed_data
cp -r "$PREPROCESSED_DATA_PATH/$TASK_TYPE/$FULL_TASK-bin" $SLURM_TMPDIR

# Re-initialize the results folder
rm -rf $RESULTS_PATH
mkdir -p $RESULTS_PATH/tensorboard_logs

# Move to SLURM temporary directory
cd $SLURM_TMPDIR

if [ $TASK_TYPE == "classification" ]
then
  # Finetuning parameters
  MAX_EPOCHS=3  # Defautl: 10
  MAX_SENTENCES=32  # Default: 32
  UPDATE_FREQ=1  # Default: 1
  LR=1e-05
  WARMUP_UPDATES_PERCENT=6

  if [ $TASK == "context-free-same-type" ]
  then
    NUM_UPDATES_PER_EPOCH=9400  # unknown
  elif [ $TASK == "context-dependent-same-type" ]
  then
    NUM_UPDATES_PER_EPOCH=9400
  fi

  TOTAL_NUM_UPDATES=$(($NUM_UPDATES_PER_EPOCH * $MAX_EPOCHS))
  WARMUP_UPDATES=$(($WARMUP_UPDATES_PERCENT * $TOTAL_NUM_UPDATES / 100))

  # Print the parameters
  echo "Finetuning parameters:"; echo $MAX_EPOCHS; echo $MAX_SENTENCES; echo $UPDATE_FREQ;
  echo $LR; echo $WARMUP_UPDATES_PERCENT; echo $NUM_UPDATES_PER_EPOCH; echo

  CUDA_VISIBLE_DEVICES=0,1 python $MASTER_THESIS_PATH/fairseq/train.py "$FULL_TASK-bin" \
      --max-epoch $MAX_EPOCHS \
      --max-sentences $MAX_SENTENCES \
      --max-tokens 1024 \
      --update-freq $UPDATE_FREQ \
      --lr-scheduler polynomial_decay \
      --lr $LR \
      --total-num-update $TOTAL_NUM_UPDATES \
      --warmup-updates $WARMUP_UPDATES \
      --restore-file $BART/model.pt \
      --save-dir $RESULTS_PATH \
      --tensorboard-logdir $RESULTS_PATH/tensorboard_logs \
      --task sentence_prediction \
      --add-prev-output-tokens \
      --layernorm-embedding \
      --share-all-embeddings \
      --share-decoder-input-output-embed \
      --reset-optimizer \
      --reset-dataloader \
      --reset-meters \
      --required-batch-size-multiple 1 \
      --init-token 0 \
      --arch bart_large \
      --criterion sentence_prediction \
      --num-classes 2 \
      --dropout 0.1 \
      --attention-dropout 0.1 \
      --weight-decay 0.01 \
      --optimizer adam \
      --adam-betas "(0.9, 0.98)" \
      --adam-eps 1e-08 \
      --clip-norm 0.0 \
      --best-checkpoint-metric accuracy \
      --maximize-best-checkpoint-metric \
      --memory-efficient-fp16 \
      --keep-best-checkpoints 0 \
      --no-last-checkpoints \
      --find-unused-parameters;

elif [ $TASK_TYPE == "generation" ]
then
  # Finetuning parameters
  MAX_EPOCHS=5
  MAX_SENTENCES=64
  UPDATE_FREQ=4
  LR=3e-05
  WARMUP_UPDATES_PERCENT=6

  if [ $TASK == "context-free-same-type" ]
  then
    NUM_UPDATES_PER_EPOCH=249
  elif [ $TASK == "context-dependent-same-type" ]
  then
    NUM_UPDATES_PER_EPOCH=210
  fi

  TOTAL_NUM_UPDATES=$(($NUM_UPDATES_PER_EPOCH * $MAX_EPOCHS))
  WARMUP_UPDATES=$(($WARMUP_UPDATES_PERCENT * $TOTAL_NUM_UPDATES / 100))

  # Print the parameters
  echo "Finetuning parameters:"; echo $MAX_EPOCHS; echo $MAX_SENTENCES; echo $UPDATE_FREQ;
  echo $LR; echo $WARMUP_UPDATES_PERCENT; echo $NUM_UPDATES_PER_EPOCH; echo

  # Run the finetuning
  CUDA_VISIBLE_DEVICES=0,1 python $MASTER_THESIS_PATH/fairseq/train.py "$FULL_TASK-bin" \
      --max-epoch $MAX_EPOCHS \
      --max-sentences $MAX_SENTENCES \
      --max-tokens 1024 \
      --update-freq $UPDATE_FREQ \
      --lr-scheduler polynomial_decay \
      --lr $LR \
      --total-num-update $TOTAL_NUM_UPDATES \
      --warmup-updates $WARMUP_UPDATES \
      --restore-file $BART/model.pt \
      --save-dir $RESULTS_PATH \
      --tensorboard-logdir $RESULTS_PATH/tensorboard_logs \
      --task translation \
      --source-lang source \
      --target-lang target \
      --truncate-source \
      --layernorm-embedding \
      --share-all-embeddings \
      --share-decoder-input-output-embed \
      --reset-optimizer \
      --reset-dataloader \
      --reset-meters \
      --required-batch-size-multiple 1 \
      --arch bart_large \
      --criterion label_smoothed_cross_entropy \
      --label-smoothing 0.1 \
      --dropout 0.1 \
      --attention-dropout 0.1 \
      --weight-decay 0.01 \
      --optimizer adam \
      --adam-betas "(0.9, 0.999)" \
      --adam-eps 1e-08 \
      --clip-norm 0.1 \
      --keep-best-checkpoints 0 \
      --no-last-checkpoints \
      --find-unused-parameters;
fi

echo "Done."; echo

sbatch  ~/master_thesis/shell_scripts/rank.sh $1 $2
