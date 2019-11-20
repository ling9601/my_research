import random
import numpy as np
import time
import os
import copy
from collections import deque

import torch
import torch.optim as optim
import torch.nn.functional as F

from rl_networks import Nature_CNN
from agents.base import Agent, MemoryStorer, Memory


class DDQN(Agent, MemoryStorer):
    """
    Double-Deep-Q-Learning
    almost the same implementation as the DQN-paper( Human-Level... )
    except this implementation has Double-Q-Learning and a different optimizer

    Input shape: Nx4x84x84 (N,C,H,W)

    Args:
        hparams:{'lr','gamma','memory_size','batch_size','net_size',
                memory_storation_size','state_shape','n_actions'}
    """

    def __init__(self, logger, load_model_path, hparams, gpu='0'):
        Agent.__init__(self, hparams['state_shape'],
                       hparams['n_actions'], logger)

        # Hpyerparameters
        self.hparams = hparams

        assert hparams['net_size'] in ['big', 'small', 'normal',
                                       'super'], "net_size must be one of ['big','small','normal']"
        # Create model
        self.model = Nature_CNN(
            self.hparams['n_actions'], hparams['net_size'])
        self.target = Nature_CNN(
            self.hparams['n_actions'], hparams['net_size'])

        # Load model for inference otherwies set for training
        if load_model_path:
            self.model.load_state_dict(torch.load(load_model_path))
        else:
            self.optimizer = optim.Adam(
                self.model.parameters(), lr=self.hparams['lr'])

            # Initialize the target network to the same as model network
            self.target_update()

            # Memory
            self.memories = deque(maxlen=self.hparams['memory_size'])

            if logger is not None:
                logger.set_loss_name([*self.model.metrics_names()])

        # Check gpu
        if torch.cuda.is_available:
            self.device = 'cuda:' + gpu
        else:
            self.device = 'cpu'

        print('*** device: {} ***'.format(self.device))

        self.model.to(self.device)
        self.target.to(self.device)

        # Debug
        print('*** model structure ***')
        print(self.model)

    def target_update(self):
        """ Update target network """
        self.target.load_state_dict(copy.deepcopy(self.model.state_dict()))

    def input_to_device(self, x):
        """
        x: numpy.Array
        transpose x from (N,H,W,C) to (N,C,H,W)
        then cast x to device
        """
        # scale
        x = x.astype(np.float32)/255.0
        x = torch.Tensor(x.transpose((0, 3, 1, 2))).to(self.device)
        return x

    def memorize(self, s, a, r, s_):
        """ Add memory """
        self.memories.append(Memory(s, a, r, s_))

    def select_action(self, state):
        state = self.input_to_device(np.expand_dims(np.array(state), axis=0))
        output = self.model(state)
        action = torch.argmax(output).item()
        return action

    def learn(self):
        """ Update model network """
        # Sample from memory
        batch = random.sample(self.memories, self.hparams['batch_size'])
        s_batch, a_batch, r_batch, ns_batch = zip(*batch)

        # Data formatting
        s_batch = self.input_to_device(np.array(s_batch))
        a_batch = torch.from_numpy(
            np.array(a_batch).reshape(-1, 1)).to(device=self.device).long()
        r_batch = torch.from_numpy(
            np.array(r_batch).reshape(-1, 1)).to(device=self.device).float()
        ns_batch = self.input_to_device(np.array(ns_batch))

        # Core
        q_model = self.model(s_batch)  # (32,4) tensor
        # choose action by model-network
        action_index = torch.argmax(self.model(
            ns_batch), dim=1, keepdim=True)  # (32,1) tensor
        # compute corresponding action-value by target-network,
        q_target = self.target(ns_batch).data.cpu().numpy()

        # q_target = r if episode terminates at next_state
        zeros = np.zeros(ns_batch[0, :, :, :].shape)
        for i in range(self.hparams['batch_size']):
            if np.array_equal(ns_batch[i, :, :, :], zeros):
                q_target[i, :] = 0

        q_target = torch.from_numpy(q_target).to(device=self.device)

        q_target_sub = q_target.gather(
            1, action_index)*self.hparams['gamma'] + r_batch

        q_model_sub = q_model.gather(1, a_batch)

        # Loss
        loss = F.smooth_l1_loss(q_model_sub, q_target_sub)

        # Set gradient to zero, which need to be done
        # before starting to do backprop everytime
        self.optimizer.zero_grad()

        # Compute gradient
        loss.backward()

        # Backprop
        self.optimizer.step()

        if self.logger is not None:
            self.logger.add_loss([loss.item()])

        return loss.item()

    def save_model(self, path, info=''):
        """ save model """
        assert isinstance(info, str), 'info should be str'
        suffix = '_'+info if info else ''
        path_with_file_name = "{}/{}{}.pt".format(path, 'model', suffix)

        if os.path.exists(path_with_file_name):
            os.remove(path_with_file_name)

        torch.save(self.model.state_dict(), path_with_file_name)

    def get_memories_size(self):
        """ get the size of current memories """
        return len(self.memories)
