import theano
import theano.tensor as T
import numpy as np
from theano_toolkit import utils as U
from theano_toolkit import updates
from theano.printing import Print

def update_log_p(zeros,active,log_p_curr,log_p_prev):
    skip_idxs = T.arange((log_p_prev.shape[0] - 3)//2) * 2 + 1
    active_skip_idxs = skip_idxs[(skip_idxs < active).nonzero()]
    active_next = T.cast(T.minimum(
            T.maximum(
                active + 1,
                T.max(T.concatenate([active_skip_idxs,[-3]])) + 2 + 1
            ),
            log_p_curr.shape[0]
        ),'int32')


    common_factor = T.max(log_p_prev[:active])
    p_prev = T.exp(log_p_prev[:active] - common_factor)
    _p_prev = zeros[:active_next]
    # copy over
    _p_prev = T.set_subtensor(_p_prev[:active],p_prev)
    # previous transitions
    _p_prev = T.inc_subtensor(_p_prev[1:],_p_prev[:-1])
    # skip transitions
    _p_prev = T.inc_subtensor(_p_prev[active_skip_idxs + 2],p_prev[active_skip_idxs])
    updated_log_p_prev = T.log(_p_prev) + common_factor

    log_p_next = T.set_subtensor(
            zeros[:active_next],
            log_p_curr[:active_next] + updated_log_p_prev
        )
    return active_next,log_p_next


def path_probs(predict, Y, alpha=1e-4):
    smoothed_predict = (1 - alpha) * predict[:, Y] + alpha * np.float32(1.)/Y.shape[0]
    L = T.log(smoothed_predict)
    zeros = T.zeros_like(L[0])
    base = T.set_subtensor(zeros[:1],np.float32(1))
    log_first = zeros
    def step(log_f_curr, log_b_curr, f_active, log_f_prev, b_active, log_b_prev):
        f_active_next, log_f_next = update_log_p(zeros,f_active,log_f_curr,log_f_prev)
        b_active_next, log_b_next = update_log_p(zeros,b_active,log_b_curr,log_b_prev)
        return f_active_next, log_f_next, b_active_next, log_b_next
    [f_active,log_f_probs,b_active,log_b_probs], _ = theano.scan(
            step,
            sequences=[
                L,
                L[::-1, ::-1]
            ],
            outputs_info=[
                np.int32(1), log_first,
                np.int32(1), log_first,
            ]
        )
    idxs = T.arange(L.shape[1]).dimshuffle('x',0)
    mask = (idxs < f_active.dimshuffle(0,'x')) & (idxs < b_active.dimshuffle(0,'x'))[::-1,::-1]
    log_probs = log_f_probs + log_b_probs[::-1, ::-1] - L
    return log_probs,mask

def cost(predict, Y):
    log_probs,mask = path_probs(predict, Y)
    common_factor = T.max(log_probs)
    total_log_prob = T.log(T.sum(T.exp(log_probs - common_factor)[mask.nonzero()])) + common_factor
    return -total_log_prob


if __name__ == "__main__":
    import ctc_old
    probs = T.nnet.softmax(np.random.randn(20,11).astype(np.float32))
    labels = theano.shared(np.arange(11,dtype=np.int32))

    print ctc_old.cost(probs,labels).eval()
    print cost(probs,labels).eval()



