# encoding=utf8
import re
import random
import networkx as nx

number_regexp = re.compile(r'^-?(\d)+(\.\d+)?$')
abstract_regexp0 = re.compile(r'^([A-Z]+_)+\d+$')
abstract_regexp1 = re.compile(r'^\d0*$')
discard_regexp = re.compile(r'^n(\d+)?$')

attr_value_set = set(['-', '+', 'interrogative', 'imperative', 'expressive'])

def _is_attr_form(x):
    return (x in attr_value_set or x.endswith('_') or number_regexp.match(x) is not None)
def _is_abs_form(x):
    return (abstract_regexp0.match(x) is not None or abstract_regexp1.match(x) is not None)
def is_attr_or_abs_form(x):
    return _is_attr_form(x) or _is_abs_form(x)
def need_an_instance(x):
    return (not _is_attr_form(x) or (abstract_regexp0.match(x) is not None))

### AMR로 들어오면 일단 모든 concept에 conceptnet에서 찾을 수 있는 형식으로 바꾸어 줘야 한다.

class AMRGraph(object):

    def __init__(self, smatch_amr):
        # transform amr from original smatch format into our own data structure
        instance_triple, attribute_triple, relation_triple = smatch_amr.get_triples()
        self.root = smatch_amr.root
        self.graph = nx.DiGraph()
        self.name2concept = dict()
        self.concept2name = dict()


        # will do some adjustments
        self.abstract_concepts = dict()
        for _, name, concept in instance_triple:
            if is_attr_or_abs_form(concept):
                if _is_abs_form(concept):
                    self.abstract_concepts[name] = concept
                else:
                    print ('bad concept', _, name, concept)
            self.name2concept[name] = concept
            self.graph.add_node(name)
        for rel, concept, value in attribute_triple:
            if rel == 'TOP':
                continue
            # discard some empty names
            if rel == 'name' and discard_regexp.match(value):
                continue
            # abstract concept can't have an attribute
            if concept in self.abstract_concepts:
                print (rel, self.abstract_concepts[concept], value, "abstract concept cannot have an attribute")
                continue
            name = "%s_attr_%d"%(value, len(self.name2concept))
            if not _is_attr_form(value):
                if _is_abs_form(value):
                    self.abstract_concepts[name] = value
                else:
                    print ('bad attribute', rel, concept, value)
                    continue
            self.name2concept[name] = value
            self._add_edge(rel, concept, name)
        
        for rel, head, tail in relation_triple:
            self._add_edge(rel, head, tail)

        # lower concept
        for name in self.name2concept:
            v = self.name2concept[name]
            if not _is_abs_form(v):
                v = v.lower()
            v = v.rstrip('_')
            self.name2concept[name] = v

    def __len__(self):
        return len(self.name2concept)

    def _add_edge(self, rel, src, des):
        self.graph.add_node(src)
        self.graph.add_node(des)
        self.graph.add_edge(src, des, label=rel)
        self.graph.add_edge(des, src, label=rel + '_reverse_')
    
    def bfs(self):
        g = self.graph
        queue = [self.root]
        depths = [0]
        visited = set(queue)
        step = 0
        while step < len(queue):
            u = queue[step]
            depth = depths[step]
            step += 1
            for v in g.neighbors(u):
                if v not in visited:
                    queue.append(v)
                    depths.append(depth+1)
                    visited.add(v)
        is_connected = (len(queue) == g.number_of_nodes())
        return queue, depths, is_connected

    def local_bfs(self, g):
        queue = [self.root]
        depths = [0]
        visited = set(queue)
        step = 0
        while step < len(queue):
            u = queue[step]
            depth = depths[step]
            step += 1
            for v in g.neighbors(u):
                if v not in visited:
                    queue.append(v)
                    depths.append(depth+1)
                    visited.add(v)
        is_connected = (len(queue) == g.number_of_nodes())
        return queue, depths, is_connected


    def collect_concepts_and_relations(self):

        g = self.graph
        nodes, depths, is_connected = self.bfs()
        concepts = [self.name2concept[n] for n in nodes]

        relations = dict()
        args = list()
        for i, src in enumerate(nodes):
            relations[i] = dict()
            for j, tgt in enumerate(nodes):
                relations[i][j] = list()
                for path in nx.all_shortest_paths(g, src, tgt):
                    info = dict()

                    info['node'] = path[1:-1]
                    info['edge'] = [g[path[i]][path[i+1]]['label'] for i in range(len(path)-1)]
                    info['length'] = len(info['edge'])
                    relations[i][j].append(info)
                    # ARG0, ARG1으로 연결된 모든 노드 찾기
                    for ban in ['ARG0', 'ARG1','ARG0_reverse_', 'ARG1_reverse_']:
                    # for ban in ['ARG0', 'ARG1','ARG0_reverse_', 'ARG1_reverse_']:
                        if ban in info['edge']:
                            edge_index = [index for index, value in enumerate(info['edge']) if value == ban]
                            # print('info_edge', info['edge'])
                            # print('edge_index', edge_index)
                            # print('path', path)

                            want = [path[value + 1] for value in edge_index]
                            want2 = [path[value] for value in edge_index]
                            # print(want)
                            # print(want2)

                            args.extend([self.name2concept[n] for n in want])
                            args.extend([self.name2concept[n] for n in want2])


        # ARG에서도 -d 연결된 동사들 다 빼기
        args = list(set(args))
        new_args = []
        for ar in args:
            if (bool(bool(re.search('[-\d]', ar)))) and ar not in ['amr-unknown', 'multi-sentence', 'have-org-role']:
                try:
                    ar = ar[:ar.index('-')]

                except ValueError:
                    pass
            else:
                pass
            new_args.append(ar)
        # print(new_args, 'new_args')

        # 모든 concept에서도 -d 연결된 동사들 빼주는데 그 이유는 ConceptNet에서 찾으려고
        new_concepts = []
        for con in concepts:
            if (bool(bool(re.search('[-\d]', con)))) and con not in ['amr-unknown', 'multi-sentence', 'have-org-role']:
                try:
                    con = con[:con.index('-')]

                except ValueError:
                    pass
            else:
                pass
            new_concepts.append(con)

        return new_concepts, depths, relations, is_connected, new_args
