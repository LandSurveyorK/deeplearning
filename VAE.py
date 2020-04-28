#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 16:19:16 2020

@author: pengwei
"""

import tensorflow as tf

import numpy as np
import matplotlib.pyplot as plt
import time
from IPython import display




# Load the MNIST dataset
(train_images,_) , (test_images, _) = tf.keras.datasets.mnist.load_data()

train_images= train_images.reshape(train_images.shape[0],28,28,1).astype('float32')
test_images= test_images.reshape(test_images.shape[0],28,28,1).astype('float32')

train_images /= 255.
test_images /= 255.

train_images[train_images > 0.5]  = 1
train_images[train_images <=0.5] = 0 
test_images[test_images > 0.5] = 1
test_images[test_images <= 0.5]  = 0


TRAIN_BUF  = 60000
BATCH_SIZE = 100
TEST_BUF = 10000

train_dataset = tf.data.Dataset.from_tensor_slices(train_images).shuffle(TRAIN_BUF).batch(BATCH_SIZE)
test_dataset  = tf.data.Dataset.from_tensor_slices(test_images).shuffle(TEST_BUF).batch(BATCH_SIZE)


class VAE(tf.keras.Model):
    def __init__(self, latent_dim):
        super(VAE, self).__init__()
        self.latent_dim = latent_dim
        
        self.inference_net = tf.keras.Sequential(
            [
                tf.keras.layers.InputLayer(input_shape=(28,28,1)),
                tf.keras.layers.Conv2D(
                        filters = 32, 
                        kernel_size = 3, 
                        strides = (2,2), 
                        activation='relu'),
                tf.keras.layers.Conv2D(
                        filters = 64,
                        kernel_size = 3, 
                        strides = (2,2), 
                        activation='relu'),
                tf.keras.layers.Flatten(),
                tf.keras.layers.Dense(latent_dim + latent_dim)
            ]
        )
        
        self.generative_net = tf.keras.Sequential(
            [
                tf.keras.layers.InputLayer(input_shape=(latent_dim,)),
                tf.keras.layers.Dense(units=7*7*32, activation=tf.nn.relu),
                tf.keras.layers.Reshape(target_shape=(7,7,32)),
                tf.keras.layers.Conv2DTranspose(
                        filters = 64,
                        kernel_size = 3,
                        strides = (2,2),
                        padding = 'SAME',
                        activation='relu'),
                tf.keras.layers.Conv2DTranspose(
                        filters = 32,
                        kernel_size = 3,
                        strides = (2,2),
                        padding = 'SAME',
                        activation = 'relu'),
                tf.keras.layers.Conv2DTranspose(
                        filters = 1, 
                        kernel_size = 3,
                        strides = (1,1),
                        padding = 'SAME')
            ]                          
        )
        
    def sample(self, eps=None):
        if eps is None:
            eps = tf.random.normal(shape=(100, self.latent_dim))
        return self.decode(eps,apply_sigmoid=True)
        
        
        
    # q(z|x,phi), to get phi
    def encode(self,x):
        mean, logvar = tf.split(self.inference_net(x), num_or_size_splits = 2, axis = 1)
        return mean, logvar
    # sample z from q(z|x,\phi)
    def reparameterize(self, mean, logvar):
        eps = tf.random.normal(shape=mean.shape)
        return eps * tf.exp(logvar * 0.5)  + mean
        
    def decode(self, z, apply_sigmoid=False):
        logits = self.generative_net(z)
        if apply_sigmoid:
            probs = tf.sigmoid(logits)
            return probs
        
        return logits
                
                
                


def log_normal_pdf(sample, mean, logvar, raxis = 1):
    log2pi = tf.math.log(2 * np.pi)
    return tf.reduce_sum(
            log2pi - 0.5 *((sample-mean)**2 * tf.exp(-logvar) + logvar), axis=raxis)
    
@tf.function  
def compute_loss(model, x):
    mean, logvar = model.encode(x)
    z = model.reparameterize(mean, logvar) # sample z from q(z|x, phi)
    x_logit = model.decode(z) # p(x|z,\phi)
    
    cross_ent = tf.nn.sigmoid_cross_entropy_with_logits(logits=x_logit, labels = x)
    logpx_z = -tf.reduce_sum(cross_ent, axis=[1,2,3])
    logpz = log_normal_pdf(z,0.,0.)
    logqz_x = log_normal_pdf(z, mean, logvar)
    
    return -tf.reduce_mean(logpx_z + logpz - logqz_x)
    
@tf.function
def compute_apply_gradients(model, x, optimizer):
    with tf.GradientTape() as tape:
        loss = compute_loss(model, x)
        gradients = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(gradients, model.trainable_variables))
        

def generate_and_save_images(model, epoch, test_input):
    predictions = model.sample(test_input)
    fig = plt.figure(figsize=(4,4))
    
    for i in range(predictions.shape[0]):
        plt.subplot(4,4,i+1)
        plt.imshow(predictions[i,:,:,0], cmap='gray')
        plt.axis('off')
        
    plt.show()



###############################################################################


epochs = 10
latent_dim = 50
num_examples_to_generate = 16
random_vector_for_generation = tf.random.normal(
        shape=(num_examples_to_generate, latent_dim))

model = VAE(latent_dim)
optimizer = tf.keras.optimizers.Adam(1e-4)



# train the model 

generate_and_save_images(model, 0, random_vector_for_generation)
    

for epoch in range(1, epochs + 1):
    start_time = time.time()
    for train_x in train_dataset:
        compute_apply_gradients(model, train_x, optimizer)
    end_time = time.time()
    
    if epoch % 1 == 0 :
        loss = tf.keras.metrics.Mean()
        for test_x in test_dataset:
            loss(compute_loss(model,test_x))
        ELBO = -loss.result()
        display.clear_output(wait=False)
        print('Epoch: {}, Test set ELBO: {},'
                  'time elapse for current epoch {}'.format(
                    epoch, ELBO, end_time-start_time))
        generate_and_save_images(
                model, epoch, random_vector_for_generation)
            

    
    
    