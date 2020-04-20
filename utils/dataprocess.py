"""Dataset creation and transformations."""

import numpy as np
import tensorflow as tf

def count_lines(filename):
  """Returns the number of lines of the file :obj:`filename`."""
  with open(filename, mode="rb") as f:
    i = 0
    for i, _ in enumerate(f):
      pass
    return i + 1

def make_batch_per_replica_1_(num_replicas_in_sync):
  def fixing_shape(*args):
    src, tgt = args
    new_src = {}
    new_tgt = {}
    for feature in list(src.keys()):
      batch = src[feature]
      dim = batch.shape.ndims
      if dim==2:
        batch = tf.expand_dims(batch,0)
        new_batch = tf.reshape(batch,[-1,tf.shape(batch)[1]//num_replicas_in_sync,tf.shape(batch)[-1]])
        new_src.update({feature:new_batch})
    for feature in list(tgt.keys()):
      batch = tgt[feature]
      dim = batch.shape.ndims
      if dim==2:
        batch = tf.expand_dims(batch,0)
        new_batch = tf.reshape(batch,[-1,tf.shape(batch)[1]//num_replicas_in_sync,tf.shape(batch)[-1]])
        new_tgt.update({feature:new_batch})
    return new_src, new_tgt
  return fixing_shape

def make_batch_per_replica_(num_replicas_in_sync):
  def fixing_shape(*args):
    src, tgt = args
    new_src = {}
    new_tgt = {}
    for feature in list(src.keys()):
      batch = src[feature]
      dim = batch.shape.ndims
      if dim==1:
        batch = tf.expand_dims(batch,0)
        new_batch = tf.reshape(batch,[num_replicas_in_sync,-1])
      elif dim==2:
        batch = tf.expand_dims(batch,0)
        new_batch = tf.reshape(batch,[num_replicas_in_sync,-1,tf.shape(batch)[-1]])
      new_src.update({feature:new_batch})
    for feature in list(tgt.keys()):
      batch = tgt[feature]
      dim = batch.shape.ndims
      if dim==1:
        batch = tf.expand_dims(batch,0)
        new_batch = tf.reshape(batch,[num_replicas_in_sync,-1])
      elif dim==2:
        batch = tf.expand_dims(batch,0)
        new_batch = tf.reshape(batch,[num_replicas_in_sync,-1,tf.shape(batch)[-1]])
      new_tgt.update({feature:new_batch})
    return new_src, new_tgt
  return fixing_shape

def merge_map_fn(*args):
  
  src_batches = []
  tgt_batches = []
  for (src,tgt) in args:
    src_batches.append(src)
    tgt_batches.append(tgt)
  print("element numb: ",len(src_batches))
  src_batch = {}
  tgt_batch = {}
  #print(src_batches[0].keys())
  for feature in list(src_batches[0].keys()):
    if feature!="ids" and feature!="tokens":
      #print(feature, src_batches[0][feature])
      src_batch.update({feature: tf.concat([b[feature] for b in src_batches],0)})
    else:
      #print(feature, src_batches[0][feature])
      len_max = tf.reduce_max([tf.shape(batch[feature])[1] for batch in src_batches])
      if src_batches[0][feature].dtype == tf.string:
        src_batch.update({feature: tf.concat([tf.concat([batch[feature], tf.fill([tf.shape(batch[feature])[0], 
                                              len_max-tf.shape(batch[feature])[1]],"")],1) for batch in src_batches],0)})
      else:
        src_batch.update({feature: tf.concat([tf.concat([batch[feature], tf.cast(tf.fill([tf.shape(batch[feature])[0], 
                                              len_max-tf.shape(batch[feature])[1]],0),tf.int64)],1) for batch in src_batches],0)})
    
  for feature in list(tgt_batches[0].keys()):
    if feature!="ids" and feature!="tokens" and feature!="ids_out":
      #print(feature, tgt_batches[0][feature])
      tgt_batch.update({feature: tf.concat([b[feature] for b in tgt_batches],0)})    
    else:
      #print(feature, tgt_batches[0][feature])
      len_max = tf.reduce_max([tf.shape(batch[feature])[1] for batch in tgt_batches])
      if tgt_batches[0][feature].dtype == tf.string:
        tgt_batch.update({feature: tf.concat([tf.concat([batch[feature], tf.fill([tf.shape(batch[feature])[0], 
                                              len_max-tf.shape(batch[feature])[1]],"")],1) for batch in tgt_batches],0)})
      else:
        tgt_batch.update({feature: tf.concat([tf.concat([batch[feature], tf.cast(tf.fill([tf.shape(batch[feature])[0], 
                                              len_max-tf.shape(batch[feature])[1]],0),tf.int64)],1) for batch in tgt_batches],0)})
  #print(src_batch,tgt_batch)
  return src_batch, tgt_batch

def ragged_map(*args):
  src, tgt = args  
  src_batch = {}
  tgt_batch = {}
  for feature in list(src.keys()):
    src_batch.update({feature: tf.RaggedTensor.from_tensor(tf.expand_dims(src[feature],0))})
    
  for feature in list(tgt.keys()):
    tgt_batch.update({feature: tf.RaggedTensor.from_tensor(tf.expand_dims(tgt[feature],0))})

  return src_batch, tgt_batch

def create_multi_domain_meta_trainining_dataset(strategy, model, domain, source_file, target_file, batch_meta_train_size, batch_meta_test_size, batch_type, shuffle_buffer_size, maximum_length, picking_prob=None):
  meta_train_datasets = [] 
  meta_test_datasets = [] 
  print("batch_type: ", batch_type)
  for i, src,tgt in zip(domain,source_file,target_file):
    meta_train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_meta_train_size,
              batch_type=batch_type,
              batch_multiplier=1,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))

    meta_test_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size= batch_meta_test_size,
              batch_type=batch_type,
              batch_multiplier=1,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  if picking_prob=="Natural":
    datasets_size = [count_lines(src) for src in source_file]
    picking_prob = [data_size/sum(datasets_size) for data_size in datasets_size]
    #picking_prob = [1.0,0.01,0.01,0.01,0.01,0.01]
    print("picking probability: ", picking_prob)
  elif picking_prob=="Anneal":
    import itertools
    datasets_size = [count_lines(src) for src in source_file]
    picking_prob_ = [data_size/sum(datasets_size) for data_size in datasets_size]
    def anneal(i, end=200000 * strategy.num_replicas_in_sync):
      i = (end-i)/end
      prob_ = [p**i  for p in picking_prob_]
      return [p/sum(prob_) for p in prob_]
    tensor = tf.Variable(np.array([anneal(i) for i in range(200000)]))
    picking_prob = tf.data.Dataset.from_tensor_slices(tensor)
    print("picking probability: ", picking_prob)
  else:
    print("picking probability: ", picking_prob)

  meta_train_dataset = tf.data.experimental.sample_from_datasets(meta_train_datasets, weights=None) #tf.data.Dataset.zip(tuple(meta_train_datasets)).map(merge_map_fn) #tf.data.experimental.sample_from_datasets(meta_train_datasets)
  meta_test_dataset = tf.data.experimental.sample_from_datasets(meta_test_datasets, weights=picking_prob) #tf.data.Dataset.zip(tuple(meta_test_datasets)).map(merge_map_fn)
  
  with strategy.scope():    
    meta_train_base_dataset = meta_train_dataset      
    meta_train_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: meta_train_base_dataset)
  with strategy.scope():
    meta_test_base_dataset = meta_test_dataset      
    meta_test_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: meta_test_base_dataset)
  
  return meta_train_dataset, meta_test_dataset

def create_multi_domain_meta_trainining_dataset_v1(strategy, model, domain, source_file, target_file, batch_meta_train_size, batch_meta_test_size, batch_type, shuffle_buffer_size, maximum_length):
  meta_train_datasets = [] 
  meta_test_datasets = [] 
  print("batch_type: ", batch_type)
  datasets_size = [count_lines(src) for src in source_file]
  datasets_numb = len(source_file)
  batch_size_ratios = [data_size/sum(datasets_size) for data_size in datasets_size]
  meta_train_batches_size = [round(batch_meta_train_size * datasets_numb * ratio) for ratio in batch_size_ratios]
  meta_test_batches_size = [round(batch_meta_test_size * datasets_numb * ratio) for ratio in batch_size_ratios]
  print("meta_train_batches_size per domain: ", meta_train_batches_size)
  print("meta_test_batches_size per domain: ", meta_test_batches_size)
  for i, src,tgt in zip(domain,source_file,target_file):
    meta_train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=meta_train_batches_size[i],
              batch_type=batch_type,
              batch_multiplier=1,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))

    meta_test_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size= meta_test_batches_size[i],
              batch_type=batch_type,
              batch_multiplier=1,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  
  meta_train_dataset = tf.data.experimental.sample_from_datasets(meta_train_datasets) #tf.data.Dataset.zip(tuple(meta_train_datasets)).map(merge_map_fn) #tf.data.experimental.sample_from_datasets(meta_train_datasets)
  meta_test_dataset = tf.data.experimental.sample_from_datasets(meta_test_datasets) #tf.data.Dataset.zip(tuple(meta_test_datasets)).map(merge_map_fn)
  
  with strategy.scope():    
    meta_train_base_dataset = meta_train_dataset      
    meta_train_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: meta_train_base_dataset)
  with strategy.scope():
    meta_test_base_dataset = meta_test_dataset      
    meta_test_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: meta_test_base_dataset)
  
  return meta_train_dataset, meta_test_dataset

def create_meta_trainining_dataset(strategy, model, domain, source_file, target_file, batch_meta_train_size, batch_meta_test_size, batch_type, shuffle_buffer_size, maximum_length):
  meta_train_datasets = [] 
  meta_test_datasets = [] 
  for i, src,tgt in zip(domain,source_file,target_file):
    meta_train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_meta_train_size,
              batch_type=batch_type,              
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))

    meta_test_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size= batch_meta_test_size,
              batch_type=batch_type,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  
  meta_train_dataset = tf.data.Dataset.zip(tuple(meta_train_datasets)).map(merge_map_fn) #tf.data.experimental.sample_from_datasets(meta_train_datasets)
  meta_test_dataset = tf.data.Dataset.zip(tuple(meta_test_datasets)).map(merge_map_fn)
  with strategy.scope():
    base_dataset = meta_train_dataset      
    meta_train_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: base_dataset)
    base_dataset = meta_test_dataset      
    meta_test_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: base_dataset)

  return meta_train_dataset, meta_test_dataset

def create_trainining_dataset(strategy, model, domain, source_file, target_file, batch_train_size, batch_type, shuffle_buffer_size, maximum_length, single_pass=False, length_bucket_width=None, multi_domain=True, picking_prob=None):

  train_datasets = [] 
  if multi_domain:
    print(batch_type)
    for i,src,tgt in zip(domain,source_file,target_file):
      train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_train_size,
              batch_type=batch_type,
              domain=i,
              single_pass=single_pass,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=length_bucket_width,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  else:
    for src,tgt in zip(source_file,target_file):
      train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_train_size,
              batch_type=batch_type,
              single_pass=single_pass,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=length_bucket_width,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  
  if picking_prob=="Natural":
    datasets_size = [count_lines(src) for src in source_file]
    picking_prob = [data_size/sum(datasets_size) for data_size in datasets_size]
    print("picking probability: ", picking_prob)
  elif picking_prob=="Anneal":
    import itertools
    datasets_size = [count_lines(src) for src in source_file]
    picking_prob_ = [data_size/sum(datasets_size) for data_size in datasets_size]
    def anneal(i, end=200000 * strategy.num_replicas_in_sync):
      i = (end-i)/end
      prob_ = [p**i  for p in picking_prob_]
      return [p/sum(prob_) for p in prob_]
    tensor = tf.Variable(np.array([anneal(i) for i in range(200000)]))
    picking_prob = tf.data.Dataset.from_tensor_slices(tensor)
    print("picking probability: ", picking_prob)
  else:
    print("picking probability: ", picking_prob)

  train_dataset = tf.data.experimental.sample_from_datasets(train_datasets, weights=picking_prob) #tf.data.Dataset.zip(tuple(train_datasets)).map(merge_map_fn)
  with strategy.scope():
    base_dataset = train_dataset
    train_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: base_dataset)  

  return train_dataset

def create_trainining_dataset_v1(strategy, model, domain, source_file, target_file, batch_train_size, batch_type, shuffle_buffer_size, maximum_length, multi_domain=True):

  train_datasets = [] 
  datasets_size = [count_lines(src) for src in source_file]
  datasets_numb = len(source_file)
  batch_size_ratios = [data_size/sum(datasets_size) for data_size in datasets_size]
  batches_size = [round(batch_train_size*datasets_numb*ratio) for ratio in batch_size_ratios]
  print("batch size per domain: ", batches_size)
  if multi_domain:
    for i,src,tgt in zip(domain,source_file,target_file):
      train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batches_size[i],
              batch_type=batch_type,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  else:
    for src,tgt in zip(source_file,target_file):
      train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_train_size,
              batch_type=batch_type,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  
  train_dataset = tf.data.experimental.sample_from_datasets(train_datasets) #tf.data.Dataset.zip(tuple(train_datasets)).map(merge_map_fn)
  with strategy.scope():
    base_dataset = train_dataset
    train_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: base_dataset)  

  return train_dataset

def create_trainining_dataset_v2(strategy, model, domain, source_file, target_file, batch_train_size, batch_type, shuffle_buffer_size, maximum_length, length_bucket_width, multi_domain=True):

  train_datasets = [] 
  if multi_domain:
    print("Using multi-domain inputter")
    for i,src,tgt in zip(domain,source_file,target_file):
      train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_train_size * strategy.num_replicas_in_sync,
              batch_type=batch_type,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=length_bucket_width,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  else:
    print("Using stardard inputter")
    for src,tgt in zip(source_file,target_file):
      train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_train_size * strategy.num_replicas_in_sync,
              batch_type=batch_type,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=length_bucket_width,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length))
  
  train_dataset = tf.data.experimental.sample_from_datasets(train_datasets) #tf.data.Dataset.zip(tuple(train_datasets)).map(merge_map_fn)
  with strategy.scope():
    train_dataset = strategy.experimental_distribute_dataset(train_dataset)

  return train_dataset

def create_multi_domain_meta_trainining_dataset_v2(strategy, model, domain, source_file, target_file, batch_meta_train_size, batch_meta_test_size, batch_type, shuffle_buffer_size, maximum_length, picking_prob=None):
  meta_train_datasets = [None] * len(source_file)
  meta_train_base_datasets = [None] * len(source_file)
  meta_train_data_flows = [None] * len(source_file)
  print("batch_type: ", batch_type)
  
  for i, src, tgt in zip(domain, source_file, target_file):
    meta_train_datasets[i] = model.examples_inputter.make_training_dataset(src, tgt,
              batch_size=batch_meta_train_size,
              batch_type=batch_type,
              batch_multiplier=1,
              domain=i,
              shuffle_buffer_size=shuffle_buffer_size,
              length_bucket_width=1,  # Bucketize sequences by the same length for efficiency.
              maximum_features_length=maximum_length,
              maximum_labels_length=maximum_length)  
                
    with strategy.scope():  
      meta_train_base_datasets[i] = meta_train_datasets[i]
      meta_train_data_flow = strategy.experimental_distribute_datasets_from_function(
          lambda _: meta_train_base_datasets[i])
      meta_train_data_flows[i] = meta_train_data_flow
  
  return meta_train_datasets

def create_trainining_dataset_with_domain_tag(strategy, model, domain, source_file, target_file, batch_train_size, batch_type, shuffle_buffer_size, maximum_length, single_pass=False, length_bucket_width=None, multi_domain=True, picking_prob=None):

  train_datasets = [] 
  
  for i,src,tgt in zip(domain,source_file,target_file):
    train_datasets.append(model.examples_inputter.make_training_dataset(src, tgt,
            batch_size=batch_train_size,
            batch_type=batch_type,
            domain=i,
            single_pass=single_pass,
            shuffle_buffer_size=shuffle_buffer_size,
            length_bucket_width=length_bucket_width,  # Bucketize sequences by the same length for efficiency.
            maximum_features_length=maximum_length,
            maximum_labels_length=maximum_length))

  if picking_prob=="Natural":
    datasets_size = [count_lines(src) for src in source_file]
    picking_prob = [data_size/sum(datasets_size) for data_size in datasets_size]
    print("picking probability: ", picking_prob)
  elif picking_prob=="Anneal":
    import itertools
    datasets_size = [count_lines(src) for src in source_file]
    picking_prob_ = [data_size/sum(datasets_size) for data_size in datasets_size]
    def anneal(i, end=200000 * strategy.num_replicas_in_sync):
      i = (end-i)/end
      prob_ = [p**i  for p in picking_prob_]
      return [p/sum(prob_) for p in prob_]
    tensor = tf.Variable(np.array([anneal(i) for i in range(200000)]))
    picking_prob = tf.data.Dataset.from_tensor_slices(tensor)
    print("picking probability: ", picking_prob)
  else:
    print("picking probability: ", picking_prob)

  train_dataset = tf.data.experimental.sample_from_datasets(train_datasets, weights=picking_prob) #tf.data.Dataset.zip(tuple(train_datasets)).map(merge_map_fn)
  with strategy.scope():
    base_dataset = train_dataset
    train_dataset = strategy.experimental_distribute_datasets_from_function(
          lambda _: base_dataset)  

  return train_dataset

def meta_learning_function_on_next(metatrain_dataset, metatest_dataset, as_numpy=False):
    
  def decorator(func):
    def _fun():
      metatrain_iterator = iter(metatrain_dataset)
      metatest_iterator = iter(metatest_dataset)
      @tf.function
      def _tf_fun():
        return func(lambda: next(metatrain_iterator)+next(metatest_iterator))

      while True:
        try:
          outputs = _tf_fun()
          if as_numpy:
            outputs = tf.nest.map_structure(lambda x: x.numpy(), outputs)
          yield outputs
        except tf.errors.OutOfRangeError:
          break

    return _fun

  return decorator