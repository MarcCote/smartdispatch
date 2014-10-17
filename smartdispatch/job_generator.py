from __future__ import absolute_import

import os

from smartdispatch.pbs import PBS
from smartdispatch import get_available_queues
from smartdispatch import utils


def job_generator_factory(queue, commands, command_params={}, cluster_name=None):
    if cluster_name == "guillimin":
        return GuilliminJobGenerator(queue, commands, command_params)

    return JobGenerator(queue, commands, command_params)


class JobGenerator:
    """ Offers functionalities to generate PBS files for a given queue.

    Parameters
    ----------
    queue : dict
        information about the queue
    commands : list of str
        commands to put in PBS files
    command_params : dict
        information about the commands
    """
    def __init__(self, queue, commands, command_params={}):
        self.commands = commands

        self.queue_name = queue['queue_name']
        self.walltime = queue.get('walltime')
        self.nb_cores_per_node = queue.get('nb_cores_per_node')
        self.nb_gpus_per_node = queue.get('nb_gpus_per_node')
        self.mem_per_node = queue.get('mem_per_node')
        self.modules = queue.get('modules')

        available_queues = get_available_queues()
        if self.queue_name in available_queues:
            queue_infos = available_queues[self.queue_name]

            if self.walltime is None:
                self.walltime = queue_infos['max_walltime']
            if self.nb_cores_per_node is None:
                self.nb_cores_per_node = queue_infos['cores']
            if self.nb_gpus_per_node is None:
                self.nb_gpus_per_node = queue_infos.get('gpus', 0)
            if self.modules is None:
                self.modules = queue_infos.get('modules', [])
            if self.mem_per_node is None:
                self.mem_per_node = queue_infos.get['ram']

        if self.nb_gpus_per_node is None:
            self.nb_gpus_per_node = 0

        if self.modules is None:
            self.modules = []

        self.nb_cores_per_command = command_params.get('nb_cores_per_command', 1)
        self.nb_gpus_per_command = command_params.get('nb_gpus_per_command', 1)
        #self.mem_per_command = command_params.get('mem_per_command', 0.0)

    def generate_pbs(self):
        """ Generates PBS files allowing the execution of every commands on the given queue. """
        nb_commands_per_node = self.nb_cores_per_node//self.nb_cores_per_command

        if self.nb_gpus_per_node > 0 and self.nb_gpus_per_command > 0:
            nb_commands_per_node = min(nb_commands_per_node, self.nb_gpus_per_node//self.nb_gpus_per_command)

        pbs_files = []
        # Distribute equally the jobs among the PBS files and generate those files
        for i, commands in enumerate(utils.chunks(self.commands, n=nb_commands_per_node)):
            pbs = PBS(self.queue_name, self.walltime)

            # Set resource: nodes
            resource = "1:ppn={ppn}".format(ppn=len(commands)*self.nb_cores_per_command)
            if self.nb_gpus_per_node > 0:
                resource += ":gpus={gpus}".format(gpus=len(commands)*self.nb_gpus_per_command)

            pbs.add_resources(nodes=resource)

            pbs.add_modules_to_load(*self.modules)
            pbs.add_commands(*commands)

            pbs_files.append(pbs)

        return pbs_files

    def write_pbs_files(self, pbs_dir="./"):
        """ Writes PBS files allowing the execution of every commands on the given queue.

        Parameters
        ----------
        pbs_dir : str
            folder where to save pbs files
        """
        pbs_list = self.generate_pbs()
        pbs_filenames = []
        for i, pbs in enumerate(pbs_list):
            pbs_filename = os.path.join(pbs_dir, 'job_commands_' + str(i) + '.sh')
            pbs.save(pbs_filename)
            pbs_filenames.append(pbs_filename)

        return pbs_filenames


class GuilliminJobGenerator(JobGenerator):
    def generate_pbs(self, *args, **kwargs):
        pbs_list = JobGenerator.generate_pbs(self, *args, **kwargs)

        if 'HOME_GROUP' not in os.environ:
            raise ValueError("Undefined environment variable: $HOME_GROUP. Please, provide your account name if on Guillimin!")

        account_name = os.path.split(os.getenv('HOME_GROUP', ''))[-1]
        for pbs in pbs_list:
            pbs.add_options(A=account_name)

        return pbs_list
