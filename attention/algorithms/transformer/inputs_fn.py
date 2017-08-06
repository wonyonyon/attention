import tensorflow as tf


def filter_and_modify_dialogue(dialogue):
    # Remove single role dialogues
    if len(set([utterance.metadata["role"] for utterance in dialogue.utterances])) < 2:
        return None

    new_dialogue = type(dialogue)()
    last_role = None
    for utterance in dialogue.utterances:
        new_role = utterance.metadata["role"]
        if last_role != new_role:
            if last_role is not None:
                new_dialogue.utterances.append(last_utterance)
            last_role = new_role
            last_utterance = utterance
        else:
            last_utterance.tokenized.extend(utterance.tokenized)
    new_dialogue.utterances.append(last_utterance)
    return new_dialogue


def create_sample(dialogue_gen):
    for dialogue in dialogue_gen:
        dialogue = filter_and_modify_dialogue(dialogue)
        if dialogue is None:
            continue
        features = {"context": None, "answer": None}

        for utterance in dialogue.utterances:
            if features["context"] is None:
                features["context"] = utterance.tokenized
            else:
                features["answer"] = utterance.tokenized
                yield features
                features["context"] = features["answer"]
                features["answer"] = None


def create_textline_file(dialogue_gen, context_filename, answer_filename):
    with open(context_filename, "w") as context_file, open(answer_filename, "w") as answer_file:
        for features in create_sample(dialogue_gen):
            context_file.write(" ".join([str(x) for x in features["context"]]) + "\n")
            answer_file.write(" ".join([str(x) for x in features["answer"]]) + "\n")


def get_input_fn(batch_size, num_epochs, context_filename, answer_filename, max_sequence_len=50):
    def input_fn():
        source_dataset = tf.contrib.data.TextLineDataset(context_filename)
        target_dataset = tf.contrib.data.TextLineDataset(answer_filename)

        def map_dataset(dataset):
            dataset = dataset.map(lambda string: tf.string_split([string]).values)
            dataset = dataset.map(lambda token: tf.string_to_number(token, tf.int64))
            dataset = dataset.map(lambda tokens: (tokens, tf.size(tokens)))
            dataset = dataset.map(lambda tokens, size: (tokens[:max_sequence_len], tf.minimum(size, max_sequence_len)))
            dataset = dataset.map(lambda tokens, size, (tf.reshape(tokens, [max_sequence_len]), size))
            return dataset

        source_dataset = map_dataset(source_dataset)
        target_dataset = map_dataset(target_dataset)

        dataset = tf.contrib.data.Dataset.zip((source_dataset, target_dataset))
        dataset = dataset.repeat(num_epochs)
        dataset = dataset.padded_batch(batch_size,
                                       padded_shapes=((tf.TensorShape([max_sequence_len]), tf.TensorShape([])),
                                                      (tf.TensorShape([max_sequence_len]), tf.TensorShape([]))
                                                      ))

        iterator = dataset.make_one_shot_iterator()
        next_element = iterator.get_next()
        return next_element, None

    return input_fn
