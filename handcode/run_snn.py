import datareader, sharedutils, os
import torch
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from torch.utils import data as Data
from model_lif_fc import model_lif_fc

def snn_run(dataname, **new_conf):
  conf, cnf = sharedutils.read_config(), {}
  rd = datareader.ReadData("~/datasets/datafromgg")

  # get fixed dataset，fixed split
  # data_fixed = rd.get_fixed_splited_data(dataname)
  # data = data_fixed
  # mat, tag = rd.conv_graph(data_fixed)
  # tr_ind, val_ind, ts_ind = data.split_nodes().train_nodes, \
  # data.split_nodes().val_nodes, data.split_nodes().test_nodes
  # tr_val_ind = np.hstack((tr_ind,val_ind))
  # ##adding the validation data
  # # tr_val_ind = np.hstack((tr_val_ind,ts_ind[:500]))
  # # ts_ind = ts_ind[500:]

  # tr_val_mat = mat[tr_val_ind]
  # ts_mat = mat[ts_ind]
  # tr_val_tag = tag[tr_val_ind]
  # ts_tag = tag[ts_ind]


  #get raw dataset, fixed split
  data = rd.read_raw_data(dataname)
  # data = rd.get_fixed_splited_data(dataname)

  mat, tag = rd.conv_graph(data)
  mat = mat
  if dataname=="pubmed": mat = rd.normalize_col(mat)
  if dataname=="citeseer" : mat = mat+0.05

  # may be some new params
  cnf.update(conf['shared_conf'])
  cnf.update(conf['snn'][dataname])
  cnf.update(new_conf)

  cnf['log_dir'] = conf['snn']['log_dir']
  if cnf['v_reset'] == -100: cnf['v_reset'] = None
  random = True

  if random == True:
    tr_val_mat, ts_mat, tr_val_tag, ts_tag = \
    rd.get_random_splited_data(mat, tag, test_size=0.95)
    k = pd.DataFrame(mat)
    u = k.describe()
    print("tr_mat.shape()",u)

    train_data_loader, val_data_loader, test_data_loader = rd.numpy2dataloader(data,tr_val_mat, ts_mat,
      tr_val_tag, ts_tag, batch_size=cnf["batch_size"])
  else:
    k = pd.DataFrame(mat)
    u = k.describe()
    print("tr_mat.shape()",u)
    train_data_loader, val_data_loader, test_data_loader = rd.fixed_numpy2dataloader(data, mat, tag,
    batch_size=cnf["batch_size"])

  print("batch_size:", cnf["batch_size"])
  print("train, valiadation,test's batch num:", len(train_data_loader), len(val_data_loader), len(test_data_loader))
  
  n_nodes, n_feat, n_flat = mat.shape[0], mat.shape[1], 1
  print("data: %s, num_node_classes: %d" % (dataname, data.graph.num_classes))
  print(cnf)
  ret = model_lif_fc(device=cnf["device"], dataset_dir=cnf["dataset_dir"],
                     dataname=dataname, batch_size=cnf["batch_size"], 
                     learning_rate=cnf["learning_rate"], T=cnf["T"], tau=cnf["tau"], 
                     v_reset=cnf["v_reset"], v_threshold=cnf["v_threshold"],
                     train_epoch=cnf["train_epoch"], log_dir=cnf["log_dir"], n_labels=data.graph.num_classes,
                     n_dim0=n_nodes, n_dim1=n_flat, n_dim2=n_feat, train_data_loader=train_data_loader,
                     val_data_loader=val_data_loader, test_data_loader=test_data_loader)
  return ret


def model_startup(dataname, runs, **new_conf):
  scores = []
  submits = []

  conc = False
  if conc:
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(10)
    for run in range(runs):
      obj = pool.submit(snn_run, dataname, **new_conf)
      submits.append(obj)
    pool.shutdown(wait=True)
    for sub in submits:
      scores.append(sub.result())
  else:
    for run in range(runs):
      score = snn_run(dataname, **new_conf)
      scores.append(score)
  sharedutils.add_log(os.path.join("./tmpdir/snn/", "snn_search.log"), "-1.5: " + str(scores))
  return np.mean(scores), np.std(scores)

def search_params(dataname, runs, log_dir):
  params_set = {"learning_rate": np.array([0.01, 0.015, 0.02, 0.025, 0.03]),
                "T": np.array([200, 300, 400, 500]),
                # "tau": np.array([80, 100, 120]),
                # "v_reset": np.array([0.0, -1.0]),
                # "v_threshold": np.array([0.2, 0.4, 0.6, 0.8, 1.0])
                }

  best_score, std, best_params = sharedutils.grid_search(dataname, runs, params_set, model_startup)
  msg = "sgc; %s; best_score, std, best_params %s %s %s\n" % (dataname, best_score, std, best_params)
  print(msg)
  sharedutils.add_log(os.path.join(log_dir, "snn_search.log"), msg)

  
if __name__ == '__main__':
  print('* Set parameters in models_conf.json, such as device": "cuda:0"')
  do_search_params = input('search params? "yes" or "no", default("no"): ') or "no"
  dataname=input("cora/acm/citeseer/pubmed, default(cora): ") or "cora"
  runs = int(input("nums of runs, default(1): ") or "1")
  # do_search_params, dataname, runs = "no", "cora", 1

  if do_search_params == "yes":
    allconfs = sharedutils.read_config("./models_conf.json")
    search_params(dataname, runs, allconfs["snn"]["log_dir"])
  else:
    me, st = model_startup(dataname, runs)
    print("acc_averages %04d times: means: %04f std: %04f" % (runs, me, st))
