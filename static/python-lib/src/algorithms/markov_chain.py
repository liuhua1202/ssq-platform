"""
马尔可夫链算法
基于状态转移概率预测下一期号码
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm


class MarkovChainAlgorithm(BaseAlgorithm):
    """马尔可夫链算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        transition_matrix = self._build_transition_matrix()

        results = []
        for _ in range(generations):
            current_state = self._get_last_state()

            red_balls = []
            for _ in range(6):
                if current_state in transition_matrix:
                    next_states = transition_matrix[current_state]
                    if next_states:
                        states = list(next_states.keys())
                        probs = list(next_states.values())
                        total = sum(probs)
                        probs = [p/total for p in probs]
                        current_state = random.choices(states, weights=probs)[0]
                    else:
                        current_state = random.randint(1, 33)
                else:
                    current_state = random.randint(1, 33)

                if current_state not in red_balls and 1 <= current_state <= 33:
                    red_balls.append(current_state)

            while len(red_balls) < 6:
                new_ball = random.randint(1, 33)
                if new_ball not in red_balls:
                    red_balls.append(new_ball)

            red_balls = sorted(red_balls[:6])
            blue_ball = self._predict_blue_ball_markov()

            result = self._get_common_prediction_info(red_balls, blue_ball, 'markov_chain')
            result['remark'] = '基于状态转移概率'
            results.append(result)

        return results

    def _build_transition_matrix(self, window: int = 100) -> Dict[int, Dict[int, int]]:
        """构建状态转移矩阵"""
        data = self.analyzer.data
        if not data or len(data) < 2:
            return {}

        matrix = {}
        recent_data = data[:min(window, len(data))]

        for i in range(len(recent_data) - 1):
            current_balls = set(recent_data[i].get('red_balls', []))
            next_balls = set(recent_data[i+1].get('red_balls', []))

            for curr in current_balls:
                if curr not in matrix:
                    matrix[curr] = {}
                for nxt in next_balls:
                    matrix[curr][nxt] = matrix[curr].get(nxt, 0) + 1

        return matrix

    def _get_last_state(self) -> int:
        """获取最后一期的一个状态"""
        data = self.analyzer.data
        if not data:
            return random.randint(1, 33)
        last_balls = data[0].get('red_balls', [])
        return random.choice(last_balls) if last_balls else random.randint(1, 33)

    def _predict_blue_ball_markov(self) -> int:
        """基于马尔可夫链预测蓝球"""
        data = self.analyzer.data
        if not data or len(data) < 2:
            return random.randint(1, 16)

        blue_transitions = {}
        for i in range(len(data) - 1):
            curr_blue = data[i].get('blue_ball', 1)
            next_blue = data[i+1].get('blue_ball', 1)
            if curr_blue not in blue_transitions:
                blue_transitions[curr_blue] = {}
            blue_transitions[curr_blue][next_blue] = \
                blue_transitions[curr_blue].get(next_blue, 0) + 1

        last_blue = data[0].get('blue_ball', 1)

        if last_blue in blue_transitions and blue_transitions[last_blue]:
            next_blues = blue_transitions[last_blue]
            return max(next_blues.keys(), key=lambda x: next_blues[x])

        return random.randint(1, 16)
