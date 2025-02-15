
import numpy as np
import random
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelBinarizer
from sklearn.utils import shuffle
from sklearn import metrics
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix, roc_auc_score
import random
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


# def load(paths, verbose=-1):
#     '''expects images for each class in seperate dir, 
#     e.g all digits in 0 class in the directory named 0 '''
#     data = list()
#     labels = list()
#     # loop over the input images
#     for (i, imgpath) in enumerate(paths):
#         # load the image and extract the class labels
#         im_gray = cv2.imread(imgpath, cv2.IMREAD_GRAYSCALE)
#         image = np.array(im_gray).flatten()
#         label = imgpath.split(os.path.sep)[-2]
#         # scale the image to [0, 1] and add to list
#         data.append(image/255)
#         labels.append(label)
#         # show an update every `verbose` images
#         if verbose > 0 and i > 0 and (i + 1) % verbose == 0:
#             print("[INFO] processed {}/{}".format(i + 1, len(paths)))
#     # return a tuple of the data and labels
#     return data, labels


def create_clients(image_list, label_list, num_clients=10, initial='clients'):
    ''' return: a dictionary with keys clients' names and value as 
                data shards - tuple of images and label lists.
        args: 
            image_list: a list of numpy arrays of training images
            label_list:a list of binarized labels for each image
            num_client: number of fedrated members (clients)
            initials: the clients'name prefix, e.g, clients_1 
            
    '''

    #create a list of client names
    client_names = ['{}_{}'.format(initial, i+1) for i in range(num_clients)]

    #randomize the data
    data = list(zip(image_list, label_list))
    random.shuffle(data)

    #shard data and place at each client
    size = len(data)//num_clients
    shards = [data[i:i + size] for i in range(0, size*num_clients, size)]

    #number of clients must equal number of shards
    assert(len(shards) == len(client_names))

    return {client_names[i] : shards[i] for i in range(len(client_names))}




def batch_data(data_shard, bs=32):
    '''Takes in a clients data shard and create a DataLoader object off it
    args:
        shard: a data, label constituting a client's data shard
        bs: batch size
    return:
        DataLoader object'''
    # separate shard into data and labels lists
    data, label = zip(*data_shard)
    dataset = TensorDataset(torch.tensor(list(data), dtype=torch.float32), torch.tensor(list(label), dtype=torch.float32))
    return DataLoader(dataset, batch_size=bs, shuffle=True)


class SimpleMLP(nn.Module):
    def __init__(self, shape, classes):
        super(SimpleMLP, self).__init__()
        self.fc1 = nn.Linear(shape, 200)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(200, 100)
        self.relu2 = nn.ReLU()
        self.fc3 = nn.Linear(100, 50)
        self.relu3 = nn.ReLU()
        self.fc4 = nn.Linear(50, classes)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu1(x)
        x = self.fc2(x)
        x = self.relu2(x)
        x = self.fc3(x)
        x = self.relu3(x)
        x = self.fc4(x)
        x = self.sigmoid(x)
        return x
    

def weight_scalling_factor(clients_trn_data, client_name):
    client_names = list(clients_trn_data.keys())
    # get the batch size
    bs = list(clients_trn_data[client_name])[0][0].shape[0]
    # first calculate the total training data points across clients
    global_count = sum([len(clients_trn_data[client_name]) for client_name in client_names]) * bs
    # get the total number of data points held by a client
    local_count = len(clients_trn_data[client_name]) * bs
    return local_count / global_count


def sum_scaled_weights(scaled_weight_list):
    '''Return the sum of the listed scaled weights. This is equivalent to scaled avg of the weights'''
    avg_grad = [torch.stack(layer_grad).sum(dim=0) for layer_grad in zip(*scaled_weight_list)]
    return avg_grad

# def sum_scaled_weights_admm(scaled_weight_list):
#     '''Return the sum of the listed scaled weights. This is equivalent to scaled avg of the weights'''
#     avg_grad = [torch.stack(layer_grad).sum(dim=0) for layer_grad in zip(*scaled_weight_list)]
#     return avg_grad

# def update_avg_with_delta(avg_grad, delta_x_hats,num_of_client):
#     '''Update avg_grad by adding the corresponding elements from delta_x_hats'''
#     for avg_layer, delta_layers in zip(avg_grad, zip(*delta_x_hats)):
#         sum_delta_layer = torch.stack(delta_layers).sum(dim=0)
#         avg_layer += sum_delta_layer/num_of_client
    
#     return avg_grad


def scale_model_weights(weight, scalar):
    weight_final = [scalar * w for w in weight]
    return weight_final





import numpy as np
import random

def create_clients_non_iid(image_list, label_list, num_clients=10, min_samples_per_client=32, initial='clients'):
    """
    Return a dictionary with keys as clients' names and values as data shards,
    represented as tuples of images and label lists. The data distribution among
    clients is non-identically distributed (non-IID), and each client has at least
    32 data points.

    Args:
        image_list (list): A list of numpy arrays of training images.
        label_list (list): A list of binarized labels for each image.
        num_clients (int): Number of federated members (clients).
        min_samples_per_client (int): Minimum number of data points per client.
        initial (str): The clients' name prefix, e.g., 'clients_1'.

    Returns:
        dict: A dictionary mapping client names to non-IID data shards.
    """

    # Create a list of client names
    client_names = ['{}_{}'.format(initial, i + 1) for i in range(num_clients)]

    # Randomize the data
    data = list(zip(image_list, label_list))
    random.shuffle(data)

    shards = []
    for i in range(num_clients):
        # Generate a random alpha value for each client
        alpha = random.uniform(0.1, 5.0)
        
        # Define a Dirichlet distribution to sample proportions for each class within the client
        class_proportions = np.random.dirichlet([alpha] * len(set(label_list)))
        
        # Calculate the number of samples each client should get
        total_samples = len(data)
        client_samples = int((total_samples * 1.0 / num_clients) + 0.5)
        
        # Ensure each client gets at least min_samples_per_client
        client_samples = max(client_samples, min_samples_per_client)
        
        # Sample data for the current client using the class proportions
        client_data = []
        for cls in set(label_list):
            class_samples = int(client_samples * class_proportions[cls] + 0.5)
            class_data = [item for item in data if item[1] == cls][:class_samples]
            client_data.extend(class_data)
        
        shards.append(client_data)

        # Print the number of data points for each class in the current client
        class_counts = {cls: sum(1 for _, label in client_data if label == cls) for cls in set(label_list)}
        print(f"Client {client_names[i]}: {class_counts}")

    # Number of clients must equal the number of shards
    assert len(shards) == len(client_names)

    return {client_names[i]: shards[i] for i in range(num_clients)}






def test_model(X_test, Y_test, model, comm_round):
    bce = nn.BCELoss()
    with torch.no_grad():
        logits = model(X_test)
        loss = bce(logits, Y_test)
        Y_prdt = (logits > 0.5).int()
        acc = accuracy_score(Y_test.cpu().numpy(), Y_prdt.cpu().numpy())
        F1 = f1_score(Y_test.cpu().numpy(), Y_prdt.cpu().numpy(), zero_division=1)
        precision = precision_score(Y_test.cpu().numpy(), Y_prdt.cpu().numpy(), zero_division=1)
        recall = recall_score(Y_test.cpu().numpy(), Y_prdt.cpu().numpy(), zero_division=1)

        cm = confusion_matrix(Y_test.cpu().numpy(), Y_prdt.cpu().numpy())
        TP = cm[0][0]
        FN = cm[0][1]
        FP = cm[1][0]
        TN = cm[1][1]
        TPR = TP / (TP + FN)
        FPR = FP / (FP + TN)

        fpr, tpr, thresholds = metrics.roc_curve(Y_test.cpu().numpy(), logits.cpu().numpy())
        auc_value = roc_auc_score(Y_test.cpu().numpy(), logits.cpu().numpy())

        print('comm_round: {} | global_acc: {:.3%} | global_loss: {} | global_f1: {} | global_precision: {} | global_recall: {} | global_auc: {}| flobal_FPR: {} '.format(
            comm_round, acc, loss.item(), F1, precision, recall, auc_value, FPR))
    return acc, loss.item(), F1, precision, recall, auc_value, FPR