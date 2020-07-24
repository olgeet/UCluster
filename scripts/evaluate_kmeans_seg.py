import argparse
import h5py
from math import *
import subprocess
import tensorflow as tf
import numpy as np
from datetime import datetime
from sklearn import metrics
import json
import os, ast
import sys


#np.set_printoptions(threshold=sys.maxsize)
from scipy.optimize import linear_sum_assignment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.dirname(BASE_DIR))
sys.path.append(os.path.join(BASE_DIR,'..', 'models'))
sys.path.append(os.path.join(BASE_DIR,'..' ,'utils'))
#from MVA_cfg import *
import provider
import gapnet_seg as MODEL


# DEFAULT SETTINGS
parser = argparse.ArgumentParser()
parser.add_argument('--params', default='[50,1,32,64,128,128,2,64,128,128,256,256,256]', help='DNN parameters[[k,H,A,F,F,F,H,A,F,C,F]]')
parser.add_argument('--gpu', type=int, default=0, help='GPUs to use [default: 0]')
parser.add_argument('--n_clusters', type=int, default=2, help='Number of clusters [Default: 2]')
parser.add_argument('--max_dim', type=int, default=512, help='Dimension of the encoding layer [Default: 512]')
parser.add_argument('--model_path', default='../logs/PU/model.ckpt', help='Model checkpoint path')
parser.add_argument('--modeln', type=int,default=-1, help='Model number')
parser.add_argument('--nglob', type=int, default=2, help='Number of global features [default: 2]')
parser.add_argument('--batch', type=int, default=64, help='Batch Size  during training [default: 64]')
parser.add_argument('--num_point', type=int, default=500, help='Point Number [default: 500]')
parser.add_argument('--data_dir', default='../data/PU', help='directory with data [default: ../data/PU]')
parser.add_argument('--nfeat', type=int, default=8, help='Number of features [default: 8]')
parser.add_argument('--ncat', type=int, default=2, help='Number of categories [default: 2]')
parser.add_argument('--name', default="", help='name of the output file')
parser.add_argument('--h5_folder', default="../h5/", help='folder to store output files')


FLAGS = parser.parse_args()
MODEL_PATH = FLAGS.model_path
NUM_GLOB = FLAGS.nglob
params = ast.literal_eval(FLAGS.params)
DATA_DIR = FLAGS.data_dir
H5_DIR = os.path.join(BASE_DIR, DATA_DIR)
H5_OUT = FLAGS.h5_folder
if not os.path.exists(H5_OUT): os.mkdir(H5_OUT)  
FULL_TRAINING = True
RD = True
# MAIN SCRIPT
NUM_POINT = FLAGS.num_point
BATCH_SIZE = FLAGS.batch
NFEATURES = FLAGS.nfeat



NUM_CATEGORIES = FLAGS.ncat
#Only used to get how many parts per category

print('#### Batch Size : {0}'.format(BATCH_SIZE))
print('#### Point Number: {0}'.format(NUM_POINT))
print('#### Using GPUs: {0}'.format(FLAGS.gpu))
    
print('### Starting evaluation')



def cluster_acc(y_true, y_pred):
    """
    Calculate clustering accuracy. Require scikit-learn installed
    # Arguments
    y: true labels, numpy.array with shape `(n_samples,)`
    y_pred: predicted labels, numpy.array with shape `(n_samples,)`
    # Return
    accuracy, in [0,1]
    """
    y_true = y_true.astype(np.int64)
    #print(y_pred.shape,y_true.shape)
    assert y_pred.size == y_true.size
    D = max(y_pred.max(), y_true.max()) + 1
    w = np.zeros((D, D), dtype=np.int64)
    for i in range(y_pred.size):
        w[y_pred[i], y_true[i]] += 1
    ind = linear_sum_assignment(w.max() - w)
    ind = np.asarray(ind)
    ind = np.transpose(ind)
    return sum([w[i, j] for i, j in ind]) * 1.0 / y_pred.size
        


#EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'train_files_voxel_b3.txt')) # Need to create those
#EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'test_files_voxel_b3.txt')) # Need to create those



EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'evaluate_files_voxel.txt')) # Need to create those
#EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'evaluate_files_QCD.txt')) # Need to create those
#EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'evaluate_files_voxel_b1.txt')) # Need to create those
#EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'evaluate_files_voxel_b2.txt')) # Need to create those
#EVALUATE_FILES = provider.getDataFiles(os.path.join(H5_DIR, 'evaluate_files_voxel_b3.txt')) # Need to create those
#print("Loading: ",os.path.join(H5_DIR, 'evaluate_files_class.txt'))

def printout(flog, data):
    print(data)
    flog.write(data + '\n')

  
def eval():
    with tf.Graph().as_default():
        with tf.device('/gpu:'+str(FLAGS.gpu)):
            pointclouds_pl,  labels_pl, global_pl = MODEL.placeholder_inputs(BATCH_SIZE, NUM_POINT,NFEATURES,NUM_GLOB) 
            batch = tf.Variable(0, trainable=False)
            alpha = tf.placeholder(tf.float32, shape=())
            is_training_pl = tf.placeholder(tf.bool, shape=())
            pred,max_pool = MODEL.get_model(pointclouds_pl, is_training=is_training_pl,params=params,global_pl = global_pl,num_class=NUM_CATEGORIES)
            mu = tf.Variable(tf.zeros(shape=(FLAGS.n_clusters,FLAGS.max_dim)),name="mu",trainable=False) #k centroids
            #loss = MODEL.get_loss(pred, labels_pl,NUM_CATEGORIES)
            loss = MODEL.get_focal_loss(labels_pl,pred,NUM_CATEGORIES)
            kmeans_loss, stack_dist= MODEL.get_loss_kmeans(max_pool,mu, FLAGS.max_dim,
                                                           FLAGS.n_clusters,alpha)

            
            saver = tf.train.Saver()
          

    
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        config.allow_soft_placement = True
        #config.log_device_placement = False
        sess = tf.Session(config=config)
        if FULL_TRAINING:
            saver.restore(sess,os.path.join(MODEL_PATH,'cluster_dkm.ckpt'))
        else:
            saver.restore(sess,os.path.join(MODEL_PATH,'model.ckpt'))

        #saver.restore(sess,os.path.join(MODEL_PATH,'cluster_dkm.ckpt'))
        print('model restored')
        
        

        ops = {'pointclouds_pl': pointclouds_pl,
               'labels_pl': labels_pl,
               'is_training_pl': is_training_pl,
               'global_pl':global_pl,
               'mu':mu,
               'stack_dist':stack_dist,
               'kmeans_loss':kmeans_loss,
               'pred': pred,
               'alpha': alpha,
               'max_pool': max_pool,
               'loss': loss,}
            
        eval_one_epoch(sess,ops)

def get_batch(data,label,global_pl,  start_idx, end_idx):
    batch_label = label[start_idx:end_idx]
    batch_global = global_pl[start_idx:end_idx,:]
    #batch_label = label[start_idx:end_idx,:]
    batch_data = data[start_idx:end_idx,:]
    return batch_data, batch_label, batch_global

        
def eval_one_epoch(sess,ops):
    is_training = False

    total_correct = total_correct_ones =  total_seen =total_seen_ones= loss_sum =0    
    eval_idxs = np.arange(0, len(EVALUATE_FILES))
    y_assign = []
    y_glob =[]
    acc = 0
    for fn in range(len(EVALUATE_FILES)):
        current_file = os.path.join(H5_DIR,EVALUATE_FILES[eval_idxs[fn]])
        current_truth = []
        current_mass = []
        
        if RD:
            current_data,  current_cluster,current_label = provider.load_h5_data_label_seg(current_file)
        else:
            current_data, current_label = provider.load_h5(current_file,'seg')



        adds = provider.load_add(current_file,['global','masses'])
        
        if NUM_GLOB < adds['global'].shape[1]:
            print("Using less global variables than possible")
            current_glob = adds['global'][:,:NUM_GLOB]
        else:
            current_glob = adds['global']

        current_label = np.squeeze(current_label)
        
        file_size = current_data.shape[0]
        num_batches = file_size // BATCH_SIZE

        

        for batch_idx in range(num_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = (batch_idx+1) * BATCH_SIZE

            batch_data, batch_label, batch_global = get_batch(current_data, current_label, current_glob,start_idx, end_idx)

            cur_batch_size = end_idx-start_idx


            feed_dict = {ops['pointclouds_pl']: batch_data,
                         ops['global_pl']: batch_global,
                         #ops['labels_pl']: adds['masses'][start_idx:end_idx],
                         ops['labels_pl']: batch_label,
                         ops['alpha']: 100,
                         ops['is_training_pl']: is_training,
            }
            #,beforemax
            pred, dist,mu,max_pool = sess.run([ops['pred'], ops['stack_dist'],ops['mu'],
                                            ops['max_pool']],feed_dict=feed_dict)

            #print(pred)
            cluster_assign = np.zeros((cur_batch_size), dtype=int)
            if RD:
                batch_cluster = current_cluster[start_idx:end_idx]


            for i in range(cur_batch_size):
                index_closest_cluster = np.argmin(dist[:, i])
                cluster_assign[i] = index_closest_cluster
                if RD:
                    acc+=cluster_acc(batch_cluster,cluster_assign)
            if len(y_assign)==0:                
                if RD:
                    y_val=batch_cluster
                y_assign=cluster_assign
                y_pool=np.squeeze(max_pool)
            else:
                y_assign=np.concatenate((y_assign,cluster_assign),axis=0)
                y_pool=np.concatenate((y_pool,np.squeeze(max_pool)),axis=0)
            
                if RD:
                    y_val=np.concatenate((y_val,batch_cluster),axis=0)
                
                

        if len(y_glob)==0:
            y_glob = adds['global'][:num_batches*BATCH_SIZE]
            y_mass = adds['masses'][:num_batches*BATCH_SIZE]
        else:
            y_glob=np.concatenate((y_glob,adds['global'][:num_batches*BATCH_SIZE]),axis=0)
            y_mass=np.concatenate((y_mass,adds['masses'][:num_batches*BATCH_SIZE]),axis=0)
            

    with h5py.File(os.path.join(H5_OUT,'{0}.h5'.format(FLAGS.name)), "w") as fh5:        
        if RD:
            dset = fh5.create_dataset("label", data=y_val)
        dset = fh5.create_dataset("pid", data=y_assign)
        dset = fh5.create_dataset("max_pool", data=y_pool)
        dset = fh5.create_dataset("global", data=y_glob)
        dset = fh5.create_dataset("masses", data=y_mass)
        dset = fh5.create_dataset("data", data=current_data[:num_batches*BATCH_SIZE])
        


################################################          
    

if __name__=='__main__':
  eval()