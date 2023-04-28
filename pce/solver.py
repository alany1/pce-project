import itertools
import os
import sys

from params_proto import Proto, ParamsProto, PrefixProto
from potluck import PotluckGame
import pulp as pl
import numpy as np
import networkx as nx


class NoStdStreams(object):
    def __init__(self, stdout=None, stderr=None):
        self.devnull = open(os.devnull, "w")
        self._stdout = stdout or self.devnull or sys.stdout
        self._stderr = stderr or self.devnull or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        self.devnull.close()


class PotluckArgs(PrefixProto):
    """SolveArgs is a ParamsProto class that contains all the parameters
    needed for the solver.
    """

    num_players: int = 5

    # Fix this to use eval
    u = lambda x: x
    graph = None


class PotluckSolver:
    def __init__(self, gameWrapper, solver, network: nx.Graph = None):
        self.gameWrapper = gameWrapper
        self.game = gameWrapper.game
        self.solver = pl.getSolver(solver)
        self.model = pl.LpProblem("Potluck", pl.LpMaximize)
        self.profiles = list(
            itertools.product(
                range(self.gameWrapper.numActions), repeat=self.gameWrapper.numPlayers
            )
        )
        self.network = network
        assert self.network is not None, "Network cannot be None!"

    def consistentStrategies(self, profile, player, profilesToConsider):
        """
        Returns all strategy profiles consistent with the given profile for the given player's strategic information
        encoded by the network self.network.
        """

        consistent = set()
        for p in profilesToConsider:
            if all(profile[i] == p[i] for i in self.network.neighbors(player)):
                opponents = list(p)[:player] + list(p)[player + 1 :]
                consistent.add(tuple(opponents))

        return consistent

    def reduceProfiles(self, profilesToConsider):
        """
        Applies operator B_G.
        """
        reducedProfiles = []
        for profile in profilesToConsider:
            # Check if for all players, is everyone playing a network-consistent best reply.
            clear = True
            for player in range(self.gameWrapper.numPlayers):
                consistent = self.consistentStrategies(
                    profile, player, profilesToConsider
                )

                # Check if there is some viable conjecture (distribution over consistent) where profile_i is a B.R.
                isBestResponse = self.checkBestResponse(profile, player, consistent)
                print(f"Player {player} is a best response: {isBestResponse}")
                if not isBestResponse:
                    break
            else:
                # If all players are playing a network-consistent best reply, add the profile to the reduced set.
                reducedProfiles.append(profile)

        return reducedProfiles

    def checkBestResponse(self, profile, player, consistent):
        """
        Solve an LP to determine if there EXISTS some conjecture over opponents actions such that profile[i] is a BR
        for player i.
        """
        # Create the LP
        prob = pl.LpProblem("Best Response", pl.LpMaximize)

        # Create the variables. Introduce one variable for each consistent strategy profile.
        variables = []
        orderedConsistent = list(consistent)
        for p in orderedConsistent:
            variables.append(pl.LpVariable(str(p), 0, 1))

        # Create the objective function. The objective is not important as we just care about feasibility.
        prob += 0

        # Add the probability constraint that all variables must sum to 1.
        prob += sum(variables) == 1

        # Add the utility constraints. For each possible action of player i, add a constraint that the utility of
        # player i is at most the utility of profile[i].

        # For a given conjecture over opponents actions (specified by j), compute the utility of player i where i plays action profile[player]
        action_utility = sum(
            variables[j]
            * self.game[
                orderedConsistent[j][:player]
                + (profile[player],)
                + orderedConsistent[j][player:]
            ][player]
            for j in range(len(variables))
        )

        # action_utility = sum(
        #     variables[j] * self.game[profile[:player] + (profile[player],) + profile[player + 1:]][player]
        #     for j in
        #     range(len(variables)))

        for action in range(self.gameWrapper.numActions):
            prob += (
                sum(
                    variables[j]
                    * self.game[
                        orderedConsistent[j][:player]
                        + (action,)
                        + orderedConsistent[j][player:]
                    ][player]
                    for j in range(len(variables))
                )
                <= action_utility
            )

        # Solve the LP
        prob.solve(self.solver)

        # If the LP is infeasible, then there is no conjecture over opponents actions such that profile[i] is a BR.
        if prob.status == -1:
            return False

        return True

    def solve(self):
        """ """
        previous_size = float("inf")
        current_size = len(self.profiles)
        while previous_size - current_size > 0:
            previous_size = current_size
            # with NoStdStreams():
            self.profiles = self.reduceProfiles(self.profiles)
            current_size = len(self.profiles)
            print("Reduced from {} to {} profiles".format(previous_size, current_size))

        print("Exited with {} profiles".format(current_size))

        return self.profiles


if __name__ == "__main__":
    # game = PotluckGame(5)
    PotluckArgs.num_players = 5
    PotluckArgs.u = lambda x: x
    G = nx.Graph()

    # G empty
    G.add_node(0)
    G.add_node(1)
    G.add_node(2)
    G.add_node(3)
    G.add_node(4)

    # G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 0)

    game = PotluckGame(PotluckArgs.num_players, PotluckArgs.u)

    solver = PotluckSolver(game, "PULP_CBC_CMD", G)

    out = solver.solve()
    print(out)
