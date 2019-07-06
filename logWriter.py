import os
import shutil

import csv
import cv2

from keras.callbacks import TensorBoard

import tensorflow as tf


class LogWriter():
    def __init__(self, root, batch_size, histogram_freq=0, write_graph=True, write_grads=False,
                 save_model_interval=100):
        # 保存先のパス
        self.root = root

        if os.path.exists(self.root):
            shutil.rmtree(self.root)

        os.mkdir(self.root)
        os.mkdir(os.path.join(self.root, "logs"))
        os.mkdir(os.path.join(self.root, "csv"))
        os.mkdir(os.path.join(self.root, "models"))
        os.mkdir(os.path.join(self.root, "movies"))

        self.tb = TensorBoard(
            log_dir=os.path.join(self.root, "logs"),
            histogram_freq=histogram_freq,
            batch_size=batch_size,
            write_graph=write_graph,
            write_grads=write_grads
        )

        self.batch_id = 0

        # モデル保存間隔
        self.save_model_interval = save_model_interval

        self.names = None

        self.max_reward = 0
        self.iteration = 1

    def get_movie_pass(self):
        return os.path.join(self.root, "movies")

    def add_loss(self, losses):
        # lossをtensorboardに書き込み
        for loss, name in zip(losses, self.loss_names):
            summary = tf.Summary()
            # summary_value = summary.value.add()
            # summary_value.simple_value = loss
            # summary_value.tag = name

            summary.value.add(tag=name, simple_value=loss)

            self.tb.writer.add_summary(summary, self.batch_id)
            self.tb.writer.flush()

            self.tb.on_epoch_end(self.batch_id)

        # csvに出力
        with open(os.path.join(self.root, 'csv', 'loss.csv'), 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([self.batch_id, *losses])

        self.batch_id += 1

    def set_loss_name(self, names):
        self.loss_names = names
        print("loss_names: ", self.loss_names)
        # csvに出力
        with open(os.path.join(self.root, 'csv', 'loss.csv'), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.loss_names)

    def add_reward(self, episode, reward, info={}):
        # 標準出力
        print(episode, ":", reward, end="")

        for key in info.keys():
            print(", ", key, ":", info[key], end="")

        print()

        # rewardをtensorboardに書き込み
        summary = tf.Summary()
        # summary_value = summary.value.add()
        # summary_value.simple_value = reward
        # summary_value.tag = "episode_reward"

        summary.value.add(tag="episode_reward", simple_value=reward)  # change

        self.tb.writer.add_summary(summary, episode)
        self.tb.writer.flush()

        # csvに出力
        with open(os.path.join(self.root, 'csv', 'reward.csv'), 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow((episode, reward))

    def add_reward_iter(self, reward):
        if self.max_reward < reward:
            self.max_reward = reward

        # max_rewardをtensorboardに書き込み
        summary = tf.Summary()
        # summary_value = summary.value.add()
        # summary_value.simple_value = self.max_reward
        # summary_value.tag = "max_episode_reward"

        summary.value.add(tag="max_episode_reward", simple_value=self.max_reward)  # change

        self.tb.writer.add_summary(summary, self.iteration)
        self.tb.writer.flush()

        # csvに出力
        with open(os.path.join(self.root, 'csv', 'max_reward.csv'), 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow((self.iteration, self.max_reward))

        self.iteration += 1

    def save_model(self, agent, episode):
        # 途中経過保存
        if episode % self.save_model_interval == 0:
            agent.save_model(episode, os.path.join(self.root, 'models', 'model'))

    def set_model(self, model):
        self.tb.set_model(model)
