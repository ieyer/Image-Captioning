#! /usr/bin/python
# -*- coding: utf8 -*-




"""Generate captions for images by a given model."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
import os
import numpy as np

import tensorflow as tf
import tensorlayer as tl
from buildmodel import *

DIR = "/home/dsigpu4/Samba/image_captioning"

# Directory containing model checkpoints.
CHECKPOINT_DIR = DIR + "/model/train"
# Vocabulary file generated by the preprocessing script.
VOCAB_FILE = DIR + "/data/mscoco/word_counts.txt"
# JPEG image file to caption.
IMAGE_FILE="/home/dsigpu4/Samba/im2txt/im2txt/data/mscoco/raw-data/val2014/COCO_val2014_000000224477.jpg, /home/dsigpu4/Samba/im2txt/im2txt/data/mscoco/raw-data/val2014/COCO_val2014_000000192970.jpg"
# IMAGE_FILE = DIR + "/data/mscoco/raw-data/val2014/COCO_val2014_0000002244??.jpg"
# Disable GPU
# export CUDA_VISIBLE_DEVICES=""
# Enable 1 GPU
# export CUDA_VISIBLE_DEVICES=1

tf.logging.set_verbosity(tf.logging.INFO) # Enable tf.logging

max_caption_length = 20
top_k = 3

def main(_):
  # Model checkpoint file or directory containing a model checkpoint file.
  checkpoint_path = CHECKPOINT_DIR
  # Text file containing the vocabulary.
  vocab_file = VOCAB_FILE
  # File pattern or comma-separated list of file patterns of image files.
  input_files = IMAGE_FILE

  mode = 'inference'

  # Build the inference graph.
  g = tf.Graph()
  with g.as_default():
    images, input_seqs, target_seqs, input_mask, input_feed = Build_Inputs(mode, input_file_pattern=None)
    net_image_embeddings = Build_Image_Embeddings(mode, images, train_inception=False)
    net_seq_embeddings = Build_Seq_Embeddings(input_seqs)
    softmax, net_img_rnn, net_seq_rnn, state_feed = Build_Model(mode, net_image_embeddings, net_seq_embeddings, target_seqs, input_mask)

    if tf.gfile.IsDirectory(checkpoint_path):
      checkpoint_path = tf.train.latest_checkpoint(checkpoint_path)
      if not checkpoint_path:
        raise ValueError("No checkpoint file found in: %s" % checkpoint_path)

    saver = tf.train.Saver()
    def _restore_fn(sess):
      tf.logging.info("Loading model from checkpoint: %s", checkpoint_path)
      saver.restore(sess, checkpoint_path)
      tf.logging.info("Successfully loaded checkpoint: %s",
                      os.path.basename(checkpoint_path))

    restore_fn = _restore_fn
  g.finalize()

  # Create the vocabulary.
  vocab = tl.nlp.Vocabulary(vocab_file)

  filenames = []
  for file_pattern in input_files.split(','):
     filenames.extend(tf.gfile.Glob(file_pattern.strip()))  # Glob gets a list of file names which match the file_pattern

  tf.logging.info("Running caption generation on %d files matching %s",
                  len(filenames), input_files)

  # Generate captions
  with tf.Session(graph=g) as sess:
      # Load the model from checkpoint.
      restore_fn(sess)
      for filename in filenames:
          with tf.gfile.GFile(filename, "r") as f:
            encoded_image = f.read()    # it is string, haven't decode !
          state = sess.run(net_img_rnn.final_state,feed_dict={"image_feed:0": encoded_image})
          state = np.hstack((state.c, state.h)) # (1, 1024)

          a_id = vocab.start_id
          sentence = ''
          for _ in range(max_caption_length - 1):
              softmax_output, state = sess.run([softmax, net_seq_rnn.final_state],
                                        feed_dict={ input_feed : [a_id],
                                                    state_feed : state,
                                                    })
              state = np.hstack((state.c, state.h))
              a_id = tl.nlp.sample_top(softmax_output[0], top_k=top_k)
              word = vocab.id_to_word(a_id)
              if a_id == vocab.end_id:
                  break
              sentence += word + ' '
          print(filename)
          print(sentence)


if __name__ == "__main__":
  tf.app.run()
