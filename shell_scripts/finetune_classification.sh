#!/bin/bash
#SBATCH --job-name=tune_class
#SBATCH --partition=main
#SBATCH --gres=gpu:1
#SBATCH --mem-per-gpu=32G
#SBATCH --time=10:00:00
#SBATCH --error=/network/tmp1/jumelcle/logs/finetune_classification-%j.err
#SBATCH --output=/network/tmp1/jumelcle/logs/finetune_classification-%j.out

PREPROCESSED_DATA_PATH=/network/tmp1/jumelcle/results/preprocessed_data
MODELS_PATH=/network/tmp1/jumelcle/results/models
PRETRAINED_MODELS_PATH=/network/tmp1/jumelcle/pretrained_models
FAIRSEQ_PATH=/network/home/jumelcle/master_thesis/fairseq
TASK=classification

RESULTS_PATH="$MODELS_PATH/$TASK/$1/$2/$3"

module load miniconda
source activate nlp

cp -r "$PREPROCESSED_DATA_PATH/$TASK/$1" $SLURM_TMPDIR
cp $PRETRAINED_MODELS_PATH/$2.tar.gz $SLURM_TMPDIR
cd $SLURM_TMPDIR
tar -xvf $2.tar.gz

rm -r $RESULTS_PATH
mkdir -p $RESULTS_PATH/tensorboard_logs

MAX_EPOCHS=5  # Defautl: 10
MAX_SENTENCES=4  # Default: 32
MAX_TOKENS=1024  # Default: 1024; works: 512
UPDATE_FREQ=8  # Default: 1
LR=1e-05
#TODO
TOTAL_NUM_UPDATES=10180  # Default: 1018
WARMUP_UPDATES=610  # Default: 61
###

CUDA_VISIBLE_DEVICES=0,1 python $FAIRSEQ_PATH/train.py $1 \
    --max-epoch $MAX_EPOCHS \
    --max-sentences $MAX_SENTENCES \
    --max-tokens $MAX_TOKENS \
    --update-freq $UPDATE_FREQ \
    --lr $LR \
    --total-num-update $TOTAL_NUM_UPDATES \
    --warmup-updates $WARMUP_UPDATES \
    --restore-file $2/model.pt \
    --save-dir $RESULTS_PATH \
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
    --lr-scheduler polynomial_decay \
    --best-checkpoint-metric accuracy \
    --maximize-best-checkpoint-metric \
    --skip-invalid-size-inputs-valid-test \
    --find-unused-parameters;
    #--disable-validation \
    #--fp16 --fp16-init-scale 4 --threshold-loss-scale 1 --fp16-scale-window 128 \
