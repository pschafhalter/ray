from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pickle
import sys
import traceback

from ray.rllib.utils.policy_client import PolicyClient

if sys.version_info[0] == 2:
    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from SocketServer import TCPServer as HTTPServer
    from SocketServer import ThreadingMixIn
elif sys.version_info[0] == 3:
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn


class PolicyServer(ThreadingMixIn, HTTPServer):
    """REST server than can be launched from a ServingEnv.

    This launches a multi-threaded server that listens on the specified host
    and port to serve policy requests and forward experiences to RLlib.

    Examples:
        >>> class CartpoleServing(ServingEnv):
               def __init__(self):
                   ServingEnv.__init__(
                       self, spaces.Discrete(2),
                       spaces.Box(low=-10, high=10, shape=(4,)))
               def run(self):
                   server = PolicyServer(self, "localhost", 8900)
                   server.serve_forever()
        >>> register_env("srv", lambda _: CartpoleServing())
        >>> pg = PGAgent(env="srv", config={"num_workers": 0})
        >>> while True:
                pg.train()

        >>> client = PolicyClient("localhost:8900")
        >>> eps_id = client.start_episode()
        >>> action = client.get_action(eps_id, obs)
        >>> ...
        >>> client.log_returns(eps_id, reward)
        >>> ...
        >>> client.log_returns(eps_id, reward)
    """

    def __init__(self, serving_env, address, port):
        handler = _make_handler(serving_env)
        HTTPServer.__init__(self, (address, port), handler)


def _make_handler(serving_env):
    class Handler(SimpleHTTPRequestHandler):
        def do_POST(self):
            content_len = int(self.headers.get('Content-Length'), 0)
            raw_body = self.rfile.read(content_len)
            parsed_input = pickle.loads(raw_body)
            try:
                response = self.execute_command(parsed_input)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(pickle.dumps(response))
            except Exception:
                self.send_error(500, traceback.format_exc())

        def execute_command(self, args):
            command = args["command"]
            response = {}
            if command == PolicyClient.START_EPISODE:
                response["episode_id"] = serving_env.start_episode(
                    args["episode_id"], args["training_enabled"])
            elif command == PolicyClient.GET_ACTION:
                response["action"] = serving_env.get_action(
                    args["episode_id"], args["observation"])
            elif command == PolicyClient.LOG_ACTION:
                serving_env.log_action(
                    args["episode_id"], args["observation"], args["action"])
            elif command == PolicyClient.LOG_RETURNS:
                serving_env.log_returns(
                    args["episode_id"], args["reward"], args["info"])
            elif command == PolicyClient.END_EPISODE:
                serving_env.end_episode(
                    args["episode_id"], args["observation"])
            else:
                raise Exception("Unknown command: {}".format(command))
            return response

    return Handler
