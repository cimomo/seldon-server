import pprint
import argparse
import sys
import os
import json
from subprocess import call

import zk_utils
import seldon_utils

gdata = {
    'all_clients_node_path': "/all_clients",
}

def pp(o):
    p = pprint.PrettyPrinter(indent=4)
    p.pprint(o)

def getOpts(args):
    parser = argparse.ArgumentParser(prog='seldon-cli memcached', description='Seldon Cli')
    parser.add_argument('--action', help="the action to use", required=False)
    parser.add_argument('--client-name', help="the name of the client", required=False)
    parser.add_argument('--model-name', help="the name of the client", required=False)
    parser.add_argument('args', nargs=argparse.REMAINDER) # catch rest (non-options) as args
    opts = parser.parse_args(args)
    return opts

def is_existing_client(zkroot, client_name):
    client_names = os.listdir(zkroot + gdata["all_clients_node_path"])
    if client_name in client_names:
        return True
    else:
        return False

def write_data_to_file(data_fpath, data):
    json = seldon_utils.dict_to_json(data, True) if isinstance(data,dict) else str(data)
    seldon_utils.mkdir_p(os.path.dirname(data_fpath))
    f = open(data_fpath,'w')
    f.write(json)
    f.write('\n')
    f.close()
    print "Writing data to file[{data_fpath}]".format(**locals())

def write_node_value_to_file(zk_client, zkroot, node_path):
    node_value = zk_utils.node_get(zk_client, node_path)
    node_value = node_value.strip()
    if zk_utils.is_json_data(node_value):
        data = seldon_utils.json_to_dict(node_value) if node_value != None and len(node_value)>0 else ""
    else:
        data = str(node_value)
    data_fpath = zkroot + node_path + "/_data_"
    write_data_to_file(data_fpath, data)

def run_spark_job(command_data, job_info, client_name):
    conf_data = command_data["conf_data"]
    spark_home = conf_data["spark_home"]
    seldon_spark_home = conf_data["seldon_spark_home"]
    seldon_version = conf_data["seldon_version"]
    zk_hosts = conf_data["zk_hosts"]

    cmd = job_info["cmd"].replace("%SPARK_HOME%", spark_home)

    cmd_args = job_info["cmd_args"]

    replacements = [
        ("%CLIENT_NAME%", client_name),
        ("%SPARK_HOME%", spark_home),
        ("%SELDON_SPARK_HOME%", seldon_spark_home),
        ("%SELDON_VERSION%", seldon_version),
        ("%ZK_HOSTS%", zk_hosts),
    ]

    def appy_replacements(item):
        for rpair in replacements:
            item = item.replace(rpair[0],rpair[1])
        return item

    cmd_args = map(appy_replacements, cmd_args)

    call([cmd]+cmd_args)

def action_add(command_data, opts):
    client_name = opts.client_name
    if client_name == None:
        print "Need client name to add model for"
        sys.exit(1)

    zkroot = command_data["zkdetails"]["zkroot"]
    if not is_existing_client(zkroot, client_name):
        print "Invalid client[{client_name}]".format(**locals())
        sys.exit(1)

    model_name = opts.model_name
    if model_name == None:
        print "Need model name to use"
        sys.exit(1)

    default_models = command_data["conf_data"]["default_models"]
    if model_name not in default_models.keys():
        print "Invalid model name: {model_name}".format(**locals())
        sys.exit(1)

    data_fpath = "{zkroot}{all_clients_node_path}/{client_name}/offline/{model_name}/_data_".format(zkroot=zkroot,all_clients_node_path=gdata["all_clients_node_path"],client_name=client_name,model_name=model_name)

    zk_client = command_data["zkdetails"]["zk_client"]
    if not os.path.isfile(data_fpath):
        node_path = "{all_clients_node_path}/{client_name}/offline/{model_name}".format(all_clients_node_path=gdata["all_clients_node_path"],client_name=client_name,model_name=model_name)
        if zk_client.exists(node_path):
            write_node_value_to_file(zk_client, zkroot, node_path)
        else:
            default_model_data = default_models[model_name]["config"]
            if default_model_data.has_key("inputPath"):
                default_model_data["inputPath"]=command_data["conf_data"]["seldon_models"]
            if default_model_data.has_key("outputPath"):
                default_model_data["outputPath"]=command_data["conf_data"]["seldon_models"]
            data = default_model_data
            write_data_to_file(data_fpath, data)
            zk_utils.node_set(zk_client, node_path, seldon_utils.dict_to_json(data))
    else:
        print "Model [{model_name}] already added".format(**locals())

def action_list(command_data, opts):
    default_models = command_data["conf_data"]["default_models"]
    models = default_models.keys()
    print "models:"
    for idx,model in enumerate(models):
        print "    {model}".format(**locals())

def action_show(command_data, opts):
    def get_valid_client():
        client_name = opts.client_name
        if client_name == None:
            print "Need client name to show models for"
            sys.exit(1)

        zkroot = command_data["zkdetails"]["zkroot"]
        if not is_existing_client(zkroot, client_name):
            print "Invalid client[{client_name}]".format(**locals())
            sys.exit(1)
        return client_name
    def show_models(models_for_client_fpath):
        models = os.listdir(models_for_client_fpath)
        for idx,model in enumerate(models):
            print "    {model}".format(**locals())

    client_name = get_valid_client()

    zk_client = command_data["zkdetails"]["zk_client"]
    zkroot = command_data["zkdetails"]["zkroot"]

    models_for_client_fpath = "{zkroot}{all_clients_node_path}/{client_name}/offline".format(zkroot=zkroot,all_clients_node_path=gdata["all_clients_node_path"],client_name=client_name)

    show_models(models_for_client_fpath)

def action_edit(command_data, opts):
    zkroot = command_data["zkdetails"]["zkroot"]
    def get_valid_client():
        client_name = opts.client_name
        if client_name == None:
            print "Need client name to show models for"
            sys.exit(1)

        if not is_existing_client(zkroot, client_name):
            print "Invalid client[{client_name}]".format(**locals())
            sys.exit(1)
        return client_name

    def get_valid_model():
        model_name = opts.model_name
        if model_name == None:
            print "Need model name to use"
            sys.exit(1)

        default_models = command_data["conf_data"]["default_models"]
        if model_name not in default_models.keys():
            print "Invalid model name: {model_name}".format(**locals())
            sys.exit(1)
        return model_name

    client_name = get_valid_client()
    model_name = get_valid_model()

    zk_client = command_data["zkdetails"]["zk_client"]

    data_fpath = "{zkroot}{all_clients_node_path}/{client_name}/offline/{model_name}/_data_".format(zkroot=zkroot,all_clients_node_path=gdata["all_clients_node_path"],client_name=client_name,model_name=model_name)

    #do the edit
    editor=seldon_utils.get_editor()
    call([editor, data_fpath])

    f = open(data_fpath)
    json = f.read()
    f.close()
    data = seldon_utils.json_to_dict(json)

    if data is None:
        print "Invalid model json!"
    else:
        write_data_to_file(data_fpath, data)
        node_path = "{all_clients_node_path}/{client_name}/offline/{model_name}".format(all_clients_node_path=gdata["all_clients_node_path"],client_name=client_name,model_name=model_name)
        pp(node_path)
        zk_utils.node_set(zk_client, node_path, seldon_utils.dict_to_json(data))

def action_train(command_data, opts):
    zkroot = command_data["zkdetails"]["zkroot"]
    def get_valid_client():
        client_name = opts.client_name
        if client_name == None:
            print "Need client name to show models for"
            sys.exit(1)

        if not is_existing_client(zkroot, client_name):
            print "Invalid client[{client_name}]".format(**locals())
            sys.exit(1)
        return client_name

    def get_valid_model():
        model_name = opts.model_name
        if model_name == None:
            print "Need model name to use"
            sys.exit(1)

        default_models = command_data["conf_data"]["default_models"]
        if model_name not in default_models.keys():
            print "Invalid model name: {model_name}".format(**locals())
            sys.exit(1)
        return model_name

    client_name = get_valid_client()
    model_name = get_valid_model()

    zkroot = command_data["zkdetails"]["zkroot"]

    default_models = command_data["conf_data"]["default_models"]
    model_training = default_models[model_name]["training"]
    job_type = model_training["job_type"]
    job_info = model_training["job_info"]

    job_handlers = {
            'spark' : run_spark_job
    }

    if job_handlers.has_key(job_type):
        job_handlers[job_type](command_data, job_info, client_name)
    else:
        print "No handler found for job_type[{job_type}]".format(**locals())


def cmd_model(command_data, command_args):
    actions = {
        "default" : action_list,
        "list" : action_list,
        "add" : action_add,
        "show" : action_show,
        "edit" : action_edit,
        "train" : action_train,
    }

    opts = getOpts(command_args)

    action = opts.action
    if action == None:
        actions["default"](command_data, opts)
    else:
        if actions.has_key(action):
            actions[action](command_data, opts)
        else:
            print "Invalid action[{}]".format(action)

