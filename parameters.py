# region Miscellaneous

verbose = True
save = True

# endregion

# region Paths

modeling_task_for_baselines_path = 'results/modeling_task/baselines_split/'
modeling_task_for_models_path = 'results/modeling_task/models_split/'

baselines_results_path = 'results/baselines/'
models_results_path = 'results/models/'

# endregion

# region Annotation task parameters

# TODO

# endregion

# region Modeling task parameters

modeling_task_names = ['ContextFreeTask',
                       'ContextFreeSameTypeTask',
                       'ContextDependentTask',
                       'ContextDependentSameTypeTask',
                       'FullHybridTask',
                       'HybridTask',
                       'HybridSameTypeTask']

min_assignments = 5
min_answers = 2
batch_size = 32
drop_last = False
k_cross_validation = 0
modeling_task_random_seed = 1

evaluation_test_proportion = 0.5
evaluation_valid_proportion = 0.5

training_test_proportion = 0.25
training_valid_proportion = 0.25

# endregion

# region Baselines parameters

# TODO

# endregion

# region Models parameters

# TODO

# endregion
