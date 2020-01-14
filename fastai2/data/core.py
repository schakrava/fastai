# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_data.core.ipynb (unless otherwise specified).

__all__ = ['show_batch', 'show_results', 'TfmdDL', 'DataBunch', 'FilteredBase', 'TfmdList', 'decode_at', 'show_at',
           'DataSource', 'test_set', 'test_dl']

# Cell
from ..torch_basics import *
from .load import *

# Cell
@typedispatch
def show_batch(x, y, samples, ctxs=None, max_n=9, **kwargs):
    if ctxs is None: ctxs = Inf.nones
    for i in range_of(samples[0]):
        ctxs = [b.show(ctx=c, **kwargs) for b,c,_ in zip(samples.itemgot(i),ctxs,range(max_n))]
    return ctxs

# Cell
@typedispatch
def show_results(x, y, samples, outs, ctxs=None, max_n=9, **kwargs):
    if ctxs is None: ctxs = Inf.nones
    for i in range(len(samples[0])):
        ctxs = [b.show(ctx=c, **kwargs) for b,c,_ in zip(samples.itemgot(i),ctxs,range(max_n))]
    for i in range(len(outs[0])):
        ctxs = [b.show(ctx=c, **kwargs) for b,c,_ in zip(outs.itemgot(i),ctxs,range(max_n))]
    return ctxs

# Cell
_batch_tfms = ('after_item','before_batch','after_batch')

# Cell
@delegates()
class TfmdDL(DataLoader):
    "Transformed `DataLoader`"
    def __init__(self, dataset, bs=64, shuffle=False, num_workers=None, **kwargs):
        if num_workers is None: num_workers = min(16, defaults.cpus)
        for nm in _batch_tfms:
            kwargs[nm] = Pipeline(kwargs.get(nm,None), as_item=(nm=='before_batch'))
        super().__init__(dataset, bs=bs, shuffle=shuffle, num_workers=num_workers, **kwargs)
        for nm in _batch_tfms: kwargs[nm].setup(self)

    def _one_pass(self):
        b = self.do_batch([self.do_item(0)])
        if self.device is not None: b = to_device(b, self.device)
        its = self.after_batch(b)
        self._n_inp = 1 if not isinstance(its, (list,tuple)) or len(its)==1 else len(its)-1
        self._types = mapped(type,its)

    def _retain_dl(self,b):
        if not getattr(self, '_types', None): self._one_pass()
        return retain_types(b, typs=self._types)

    @delegates(DataLoader.new)
    def new(self, dataset=None, cls=None, **kwargs):
        res = super().new(dataset, cls, **kwargs)
        if not hasattr(self, '_n_inp') or not hasattr(self, '_types'):
            self._one_pass()
        res._n_inp,res._types = self._n_inp,self._types
        return res

    def before_iter(self):
        super().before_iter()
        split_idx = getattr(self.dataset, 'split_idx', None)
        for nm in _batch_tfms:
            f = getattr(self,nm)
            if isinstance(f,Pipeline): f.split_idx=split_idx

    def decode(self, b): return self.before_batch.decode(to_cpu(self.after_batch.decode(self._retain_dl(b))))
    def decode_batch(self, b, max_n=9, full=True): return self._decode_batch(self.decode(b), max_n, full)

    def _decode_batch(self, b, max_n=9, full=True):
        f = self.after_item.decode
        f = compose(f, partial(getattr(self.dataset,'decode',noop), full = full))
        return L(batch_to_samples(b, max_n=max_n)).map(f)

    def _pre_show_batch(self, b, max_n=9):
        "Decode `b` to be ready for `show_batch`"
        b = self.decode(b)
        if hasattr(b, 'show'): return b,None,None
        its = self._decode_batch(b, max_n, full=False)
        if not is_listy(b): b,its = [b],L((o,) for o in its)
        return detuplify(b[:self.n_inp]),detuplify(b[self.n_inp:]),its

    def show_batch(self, b=None, max_n=9, ctxs=None, show=True, **kwargs):
        if b is None: b = self.one_batch()
        if not show: return self._pre_show_batch(b, max_n=max_n)
        show_batch(*self._pre_show_batch(b, max_n=max_n), ctxs=ctxs, max_n=max_n, **kwargs)

    def show_results(self, b, out, max_n=9, ctxs=None, show=True, **kwargs):
        x,y,its = self.show_batch(b, max_n=max_n, show=False)
        b_out = b[:self.n_inp] + (tuple(out) if is_listy(out) else (out,))
        x1,y1,outs = self.show_batch(b_out, max_n=max_n, show=False)
        res = (x,x1,None,None) if its is None else (x, y, its, outs.itemgot(slice(self.n_inp,None)))
        if not show: return res
        show_results(*res, ctxs=ctxs, max_n=max_n, **kwargs)

    @property
    def n_inp(self):
        if hasattr(self.dataset, 'n_inp'): return self.dataset.n_inp
        if not hasattr(self, '_n_inp'): self._one_pass()
        return self._n_inp

# Cell
@docs
class DataBunch(GetAttr):
    "Basic wrapper around several `DataLoader`s."
    _default='train_dl'
    def __init__(self, *dls, path='.', device=None):
        self.dls,self.path = dls,Path(path)
        self.device = device

    def __getitem__(self, i): return self.dls[i]
    def new_empty(self):
        dls = [dl.new(dl.dataset.new_empty()) for dl in self.dls]
        return type(self)(*dls)

    train_dl,valid_dl = add_props(lambda i,x: x[i])
    train_ds,valid_ds = add_props(lambda i,x: x[i].dataset)

    @property
    def device(self): return self._device

    @device.setter
    def device(self, d):
        for dl in self.dls: dl.device = d
        self._device = d

    def cuda(self, device=None): self.device = default_device() if device is None else device
    def cpu(self): self.cuda(device=torch.device('cpu'))

    @classmethod
    @delegates(TfmdDL.__init__)
    def from_dblock(cls, dblock, source, path='.', type_tfms=None, item_tfms=None, batch_tfms=None, **kwargs):
        return dblock.databunch(source, path=path, type_tfms=type_tfms, item_tfms=item_tfms, batch_tfms=batch_tfms, **kwargs)

    _docs=dict(__getitem__="Retrieve `DataLoader` at `i` (`0` is training, `1` is validation)",
               train_dl="Training `DataLoader`",
               valid_dl="Validation `DataLoader`",
               train_ds="Training `Dataset`",
               valid_ds="Validation `Dataset`",
               cuda="Use `device` (defaults to `default_device()`)",
               cpu="Use the cpu",
               new_empty="Create a new empty version of `self` with the same transforms",
               from_dblock="Create a databunch from a given `dblock`")

# Cell
class FilteredBase:
    "Base class for lists with subsets"
    _dl_type = TfmdDL
    def __init__(self, *args, dl_type=None, **kwargs):
        if dl_type is not None: self._dl_type = dl_type
        self.databunch = delegates(self._dl_type.__init__)(self.databunch)
        super().__init__(*args, **kwargs)

    @property
    def n_subsets(self): return len(self.splits)
    def _new(self, items, **kwargs): return super()._new(items, splits=self.splits, **kwargs)
    def subset(self): raise NotImplemented

    def databunch(self, bs=64, val_bs=None, shuffle_train=True, n=None, path='.', dl_type=None, dl_kwargs=None, device=None,
                  **kwargs):
        if device is None: device=default_device()
        if dl_kwargs is None: dl_kwargs = [{}] * self.n_subsets
        ns = self.n_subsets-1
        bss = ([None]*(ns+1) if bs is None
               else [bs] + [3*bs//2]*ns if val_bs is None
               else [bs] + [val_bs]*ns)
        shuffles = [shuffle_train] + [False]*ns
        if dl_type is None: dl_type = self._dl_type
        dls = [dl_type(self.subset(i), bs=b, shuffle=s, drop_last=s, n=n if i==0 else None, **kwargs, **dk)
               for i,(b,s,dk) in enumerate(zip(bss,shuffles,dl_kwargs))]
        return DataBunch(*dls, path=path, device=device)

FilteredBase.train,FilteredBase.valid = add_props(lambda i,x: x.subset(i))

# Cell
class TfmdList(FilteredBase, L, GetAttr):
    "A `Pipeline` of `tfms` applied to a collection of `items`"
    _default='tfms'
    def __init__(self, items, tfms, use_list=None, do_setup=True, as_item=True, split_idx=None, train_setup=True,
                 splits=None, types=None):
        super().__init__(items, use_list=use_list)
        self.splits = L([slice(None),[]] if splits is None else splits).map(mask2idxs)
        if isinstance(tfms,TfmdList): tfms = tfms.tfms
        if isinstance(tfms,Pipeline): do_setup=False
        self.tfms = Pipeline(tfms, as_item=as_item, split_idx=split_idx)
        self.types = types
        if do_setup: self.setup(train_setup=train_setup)

    def _new(self, items, **kwargs): return super()._new(items, tfms=self.tfms, do_setup=False, types=self.types, **kwargs)
    def subset(self, i): return self._new(self._get(self.splits[i]), split_idx=i)
    def _after_item(self, o): return self.tfms(o)
    def __repr__(self): return f"{self.__class__.__name__}: {self.items}\ntfms - {self.tfms.fs}"
    def __iter__(self): return (self[i] for i in range(len(self)))
    def show(self, o, **kwargs): return self.tfms.show(o, **kwargs)
    def decode(self, o, **kwargs): return self.tfms.decode(o, **kwargs)
    def __call__(self, o, **kwargs): return self.tfms.__call__(o, **kwargs)
    def overlapping_splits(self): return L(Counter(self.splits.concat()).values()).filter(gt(1))

    def setup(self, train_setup=True):
        self.tfms.setup(self, train_setup)
        if len(self) != 0:
            x = super().__getitem__(0) if self.splits is None else super().__getitem__(self.splits[0])[0]
            self.types = []
            for f in self.tfms.fs:
                self.types.append(getattr(f, 'input_types', type(x)))
                x = f(x)
            self.types.append(type(x))
        types = L(t if is_listy(t) else [t] for t in self.types).concat().unique()
        self.pretty_types = '\n'.join([f'  - {t}' for t in types])

    def infer_idx(self, x):
        idx = 0
        for t in self.types:
            if isinstance(x, t): break
            idx += 1
        types = L(t if is_listy(t) else [t] for t in self.types).concat().unique()
        pretty_types = '\n'.join([f'  - {t}' for t in types])
        assert idx < len(self.types), f"Expected an input of type in \n{pretty_types}\n but got {type(x)}"
        return idx

    def infer(self, x):
        return compose_tfms(x, tfms=self.tfms.fs[self.infer_idx(x):], split_idx=self.split_idx)

    def __getitem__(self, idx):
        res = super().__getitem__(idx)
        if self._after_item is None: return res
        return self._after_item(res) if is_indexer(idx) else res.map(self._after_item)

# Cell
def decode_at(o, idx):
    "Decoded item at `idx`"
    return o.decode(o[idx])

# Cell
def show_at(o, idx, **kwargs):
    "Show item at `idx`",
    return o.show(o[idx], **kwargs)

# Cell
@docs
@delegates(TfmdList)
class DataSource(FilteredBase):
    "A dataset that creates a tuple from each `tfms`, passed thru `item_tfms`"
    def __init__(self, items=None, tfms=None, tls=None, n_inp=None, dl_type=None, **kwargs):
        super().__init__(dl_type=dl_type)
        self.tls = L(tls if tls else [TfmdList(items, t, **kwargs) for t in L(ifnone(tfms,[None]))])
        self.n_inp = (1 if len(self.tls)==1 else len(self.tls)-1) if n_inp is None else n_inp

    def __getitem__(self, it):
        res = tuple([tl[it] for tl in self.tls])
        return res if is_indexer(it) else list(zip(*res))

    def __getattr__(self,k): return gather_attrs(self, k, 'tls')
    def __dir__(self): return super().__dir__() + gather_attr_names(self, 'tls')
    def __len__(self): return len(self.tls[0])
    def __iter__(self): return (self[i] for i in range(len(self)))
    def __repr__(self): return coll_repr(self)
    def decode(self, o, full=True): return tuple(tl.decode(o_, full=full) for o_,tl in zip(o,tuplify(self.tls, match=o)))
    def subset(self, i): return type(self)(tls=L(tl.subset(i) for tl in self.tls), n_inp=self.n_inp)
    def _new(self, items, *args, **kwargs): return super()._new(items, tfms=self.tfms, do_setup=False, **kwargs)
    def overlapping_splits(self): return self.tls[0].overlapping_splits()
    @property
    def splits(self): return self.tls[0].splits
    @property
    def split_idx(self): return self.tls[0].tfms.split_idx
    @property
    def items(self): return self.tls[0].items
    @items.setter
    def items(self, v):
        for tl in self.tls: tl.items = v

    def show(self, o, ctx=None, **kwargs):
        for o_,tl in zip(o,self.tls): ctx = tl.show(o_, ctx=ctx, **kwargs)
        return ctx

    def new_empty(self):
        tls = [tl._new([], split_idx=tl.split_idx) for tl in self.tls]
        return type(self)(tls=tls, n_inp=self.n_inp)

    @contextmanager
    def set_split_idx(self, i):
        old_split_idx = self.split_idx
        for tl in self.tls: tl.tfms.split_idx = i
        yield self
        for tl in self.tls: tl.tfms.split_idx = old_split_idx

    _docs=dict(
        decode="Compose `decode` of all `tuple_tfms` then all `tfms` on `i`",
        show="Show item `o` in `ctx`",
        databunch="Get a `DataBunch`",
        overlapping_splits="All splits that are in more than one split",
        subset="New `DataSource` that only includes subset `i`",
        new_empty="Create a new empty version of the `self`, keeping only the transforms",
        set_split_idx="Contextmanager to use the same `DataSource` with another `split_idx`"
    )

# Cell
def test_set(dsrc, test_items, rm_tfms=None):
    "Create a test set from `test_items` using validation transforms of `dsrc`"
    test_tls = [tl._new(test_items, split_idx=1) for tl in dsrc.tls[:dsrc.n_inp]]
    if rm_tfms is None: rm_tfms = [tl.infer_idx(test_items[0]) for tl in test_tls]
    else:               rm_tfms = tuplify(rm_tfms, match=test_tls)
    for i,j in enumerate(rm_tfms): test_tls[i].tfms.fs = test_tls[i].tfms.fs[j:]
    return DataSource(tls=test_tls)

# Cell
@delegates(TfmdDL.__init__)
def test_dl(dbunch, test_items, rm_type_tfms=None, **kwargs):
    "Create a test dataloader from `test_items` using validation transforms of `dbunch`"
    test_ds = test_set(dbunch.valid_ds, test_items, rm_tfms=rm_type_tfms) if isinstance(dbunch.valid_ds, DataSource) else test_items
    return dbunch.valid_dl.new(test_ds, **kwargs)