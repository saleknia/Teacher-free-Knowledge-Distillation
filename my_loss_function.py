import torch
import torch.nn as nn
import torch.nn.functional as F

def disparity(outputs, labels):
    loss = 0.0
    B,N = outputs.shape

    mask_unique_value = torch.unique(labels)
    unique_num = len(mask_unique_value)
        
    if unique_num<2:
        return 0

    prototypes = torch.zeros(size=(unique_num,N))

    for count,p in enumerate(mask_unique_value):
        p = p.long()
        v = torch.mean(outputs[labels==p],dim=0)
        v = nn.functional.normalize(v, p=2.0, dim=0, eps=1e-12, out=None)
        prototypes[count] = v

    distances = torch.cdist(prototypes, prototypes, p=2.0)
    loss = loss + (1.0 / torch.mean(distances))

    return loss

def loss_kd_disparity(outputs, labels, params):
    """
    loss function for disparity regularization.
    """
    alpha = 0.5
    loss_CE = F.cross_entropy(outputs, labels)
    loss_disparity = disparity(outputs, labels)

    KD_loss = loss_CE + (alpha * loss_disparity)

    return KD_loss

def loss_kd(outputs, labels, teacher_outputs, params):
    """
    loss function for Knowledge Distillation (KD)
    """
    alpha = params.alpha
    T = params.temperature

    loss_CE = F.cross_entropy(outputs, labels)
    D_KL = nn.KLDivLoss()(F.log_softmax(outputs/T, dim=1), F.softmax(teacher_outputs/T, dim=1)) * (T * T)
    KD_loss =  (1. - alpha)*loss_CE + alpha*D_KL

    return KD_loss

def loss_kd_self(outputs, labels, teacher_outputs, params):
    """
    loss function for self training: Tf-KD_{self}
    """
    alpha = params.alpha
    T = params.temperature

    loss_CE = F.cross_entropy(outputs, labels)
    D_KL = nn.KLDivLoss()(F.log_softmax(outputs/T, dim=1), F.softmax(teacher_outputs/T, dim=1)) * (T * T) * params.multiplier  # multiple is 1.0 in most of cases, some cases are 10 or 50
    KD_loss =  (1. - alpha)*loss_CE + alpha*D_KL

    return KD_loss


def loss_kd_regularization(outputs, labels, params):
    """
    loss function for mannually-designed regularization: Tf-KD_{reg}
    """
    alpha = params.reg_alpha
    T = params.reg_temperature
    correct_prob = 0.99    # the probability for correct class in u(k)
    loss_CE = F.cross_entropy(outputs, labels)
    K = outputs.size(1)

    teacher_soft = torch.ones_like(outputs).cuda()
    teacher_soft = teacher_soft*(1-correct_prob)/(K-1)  # p^d(k)
    for i in range(outputs.shape[0]):
        teacher_soft[i ,labels[i]] = correct_prob
    loss_soft_regu = nn.KLDivLoss()(F.log_softmax(outputs, dim=1), F.softmax(teacher_soft/T, dim=1))*params.multiplier

    KD_loss = (1. - alpha)*loss_CE + alpha*loss_soft_regu

    return KD_loss


def loss_label_smoothing(outputs, labels):
    """
    loss function for label smoothing regularization
    """
    alpha = 0.1
    N = outputs.size(0)  # batch_size
    C = outputs.size(1)  # number of classes
    smoothed_labels = torch.full(size=(N, C), fill_value= alpha / (C - 1)).cuda()
    smoothed_labels.scatter_(dim=1, index=torch.unsqueeze(labels, dim=1), value=1-alpha)

    log_prob = torch.nn.functional.log_softmax(outputs, dim=1)
    loss = -torch.sum(log_prob * smoothed_labels) / N

    return loss
