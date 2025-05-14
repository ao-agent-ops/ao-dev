from collections import Counter
import numpy as np



class HMMLight:

    def __init__(self, n_states=2, n_observations=3, random_seed=42):
        np.random.seed(random_seed)
        self.n_states = n_states
        self.n_obs = n_observations

        # Initialize parameters randomly (rows sum to 1)
        self.pi = np.full(n_states, 1.0 / n_states) # Start.
        self.A = np.random.rand(n_states, n_states) # Transition probs
        self.A /= self.A.sum(axis=1, keepdims=True)
        self.B = np.random.rand(n_states, n_observations) # Emission probs
        self.B /= self.B.sum(axis=1, keepdims=True)


    def _forward(self, obs_seq):
        T = len(obs_seq)
        alpha = np.zeros((T, self.n_states))
        # Initialization
        alpha[0] = self.pi * self.B[:, obs_seq[0]]
        # Recursion
        for t in range(1, T):
            for j in range(self.n_states):
                alpha[t, j] = np.dot(alpha[t-1], self.A[:, j]) * self.B[j, obs_seq[t]]
        return alpha


    def _backward(self, obs_seq, final_state):
        T = len(obs_seq)
        beta = np.zeros((T, self.n_states))
        # Clamp final state
        beta[T-1] = np.array([1 if s == final_state else 0 for s in range(self.n_states)])
        # Recursion backwards
        for t in range(T-2, -1, -1):
            for i in range(self.n_states):
                beta[t, i] = np.sum(self.A[i, :] * self.B[:, obs_seq[t+1]] * beta[t+1, :])
        return beta


    def train_unsupervised(self, obs_seqs, final_labels, n_iter=10):
        """
        We only know the final state (e.g., fail/pass) and not intermediate states.

        obs_seqs: list of lists of ints (0..n_obs-1)
        final_labels: list of ints (0..n_states-1), the true hidden state at final time
        """
        for iteration in range(n_iter):
            # Expectation accumulators
            pi_acc = np.zeros(self.n_states)
            A_num = np.zeros((self.n_states, self.n_states))
            A_den = np.zeros(self.n_states)
            B_num = np.zeros((self.n_states, self.n_obs))
            B_den = np.zeros(self.n_states)

            for seq, final_state in zip(obs_seqs, final_labels):
                T = len(seq)
                alpha = self._forward(seq)
                beta = self._backward(seq, final_state)

                # Compute gamma and xi
                gamma = (alpha * beta)
                gamma /= gamma.sum(axis=1, keepdims=True)

                xi = np.zeros((T-1, self.n_states, self.n_states))
                for t in range(T-1):
                    denom = np.sum(alpha[t, :, None] * self.A * self.B[:, seq[t+1]] * beta[t+1])
                    xi[t] = (alpha[t, :, None] * self.A * self.B[:, seq[t+1]] * beta[t+1]) / denom

                # Accumulate
                pi_acc += gamma[0]
                for i in range(self.n_states):
                    A_den[i] += gamma[:-1, i].sum()
                    for j in range(self.n_states):
                        A_num[i, j] += xi[:, i, j].sum()
                for t in range(T):
                    B_den[:, seq[t]] += gamma[t]
                    for i in range(self.n_states):
                        B_num[i, seq[t]] += gamma[t, i]

            # Maximization: update parameters
            self.pi = pi_acc / pi_acc.sum()
            self.A = A_num / A_den[:, None]
            self.B = B_num / B_den[:, None]


    def predict_posteriors(self, obs_seq):
        """
        Returns the filtered posterior P(s_t | o_1:t) for each t.
        """
        alpha = self._forward(obs_seq)
        # Normalize alpha to get posteriors
        posteriors = alpha / alpha.sum(axis=1, keepdims=True)
        return posteriors


    def train_supervised(self, sequences, labels, alpha=1.0):
        # sequences: list of lists of obs indices (1..n_obs)
        # labels:    list of lists of state labels (0 or 1)
        R = len(sequences)
        # Count initial, transitions, emissions
        C_pi = Counter()
        C_A  = Counter()
        C_B  = Counter()
        for o_seq, y_seq in zip(sequences, labels):
            T = len(y_seq)
            C_pi[y_seq[0]] += 1
            for t in range(T):
                C_B[(y_seq[t], o_seq[t])] += 1
                if t < T-1:
                    C_A[(y_seq[t], y_seq[t+1])] += 1

        # Normalize
        pi = np.zeros(2)
        for i in [0,1]:
            pi[i] = (C_pi[i] + alpha) / (sum(C_pi.values()) + 2*alpha)

        A = np.zeros((2,2)) # Transition probs
        for i in [0,1]:
            row_sum = sum(C_A[(i,k)] for k in [0,1]) + 2*alpha
            for j in [0,1]:
                A[i,j] = (C_A[(i,j)] + alpha) / row_sum

        B = np.zeros((2, self.n_obs)) # Emission probs
        for i in [0,1]:
            row_sum = sum(C_B[(i,o)] for o in range(1,self.n_obs + 1)) + self.n_obs*alpha
            for o in range(1,self.n_obs+1):
                B[i,o-1] = (C_B[(i,o)] + alpha) / row_sum

        self.pi = pi
        self.A = A
        self.B = B


# Example usage:
if __name__ == "__main__":
    # Map observations to 0=C, 1=U, 2=W
    obs_seqs = [
        [0, 0, 1, 0, 0, 1, 2],  # a failed run
        [0, 0, 0, 0, 0],        # a successful run
        # ... more sequences ...
    ]
    # final_labels: 1 for fail state, 0 for pass state
    final_labels = [1, 0]
    all_labels = [
        [1, 1, 1, 0, 0, 0, 0], # a failed run
        [1, 1, 1, 1, 1] # a successful run
        # ... more sequences ...
    ]

    model = HMMLight(n_states=2, n_observations=3)
    model.train_supervised(obs_seqs, all_labels)
    # model.train_unsupervised(obs_seqs, final_labels, n_iter=20)

    # Compute posteriors on a new run
    new_seq = [0, 0, 1, 0]
    post = model.predict_posteriors(new_seq)
    print("Posterior probabilities at each step (columns are states 0=pass,1=fail):")
    print(post)
