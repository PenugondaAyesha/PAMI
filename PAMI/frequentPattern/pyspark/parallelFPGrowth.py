from pyspark import SparkConf, SparkContext
from collections import defaultdict
from PAMI.frequentPattern.pyspark import abstract as _ab
from operator import add


class _Node:
    """
        Attribute
        ---------
            item : int
                Storing item of a node
            count : int
                To maintain the support count of node
            children : dict
                To maintain the children of node
            prefix : list
                To maintain the prefix of node
    """

    def __init__(self, item, prefix):
        self.item = item
        self.count = 0
        self.children = {}
        self.prefix = prefix


class _Tree:
    """
        Attribute
        ---------
            root : Node
                The first node of the tree set to Null
            nodeLink : dict
                Store nodes that have the same item
        Methods
        -------
            addTransaction(transaction, count)
                Create tree from transaction and count
            addNodeToNodeLink(node)
                Add nodes that have the same item to self.nodeLink
            generateConditionalTree(item)
                Create conditional pattern base of item
    """

    def __init__(self):
        self.root = _Node(None, [])
        self.nodeLink = {}
        self.itemCount = defaultdict(int)

    def addTransaction(self, transaction, count):
        """
        Add transaction to tree
        :param transaction: list
        :param count: int
        :return:
        """
        current = self.root
        for item in transaction:
            if item not in current.children:
                current.children[item] = _Node(item, transaction[0:transaction.index(item)])
                current.children[item].count += count
                self.addNodeToNodeLink(current.children[item])
            else:
                current.children[item].count += count
            self.itemCount[item] += count
            current = current.children[item]

    def addNodeToNodeLink(self, node):
        """
        Add node to self.nodeLink
        :param node: Node
        :return:
        """
        if node.item not in self.nodeLink:
            self.nodeLink[node.item] = [node]
        else:
            self.nodeLink[node.item].append(node)

    def generateConditionalTree(self, item):
        """
        Generate conditional tree based on item
        :param item: str or int
        :return: Tree
        """
        tree = _Tree()
        for node in self.nodeLink[item]:
            tree.addTransaction(node.prefix, node.count)
        return tree


class parallelFPGrowth(_ab._frequentPatterns):
    """
        Attributes:
        ----------
                minSup : float
                    The user can specify minSup either in count or proportion of database size.
                iFile : file
                    Input file name or path of the input file.
                oFile : file
                    Name of the output file or the path of the output file.
                sep : str
                    This variable is used to distinguish items from one another in a transaction. The default seperator is tab space or \t.
                    However, the users can override their default separator.
                startTime:float
                    To record the start time of the mining process
                endTime:float
                    To record the completion time of the mining process
                memoryUSS : float
                    To store the total amount of USS memory consumed by the program
                memoryRSS : float
                    To store the total amount of RSS memory consumed by the program
                finalPatterns : dict
                    it represents to store the all frequent patterns
                FPList : list
                    frequent pattern list
                numWorkers: int
                    The number of workers
                    On each worker node, an executor process is started and this process performs processing.
                    The processing unit of worker node is partition
                lno : int
                    the number of transactions
            Methods
            -------
                startMine()
                    Mining process will start from this function
                getPatterns()
                    Complete set of patterns will be retrieved with this function
                save(outFile)
                    Complete set of frequent patterns will be loaded in to a output file
                getPatternsAsDataFrame()
                    Complete set of frequent patterns will be loaded in to a dataframe
                getMemoryUSS()
                    Total amount of USS memory consumed by the mining process will be retrieved from this function
                getMemoryRSS()
                    Total amount of RSS memory consumed by the mining process will be retrieved from this function
                getRuntime()
                    Total amount of runtime taken by the mining process will be retrieved from this function
                genCondTransaction(data, rank)
                    Generating conditional transactions for distributed pattern mining
                getPartitionId(item)
                    Get partition id of item
                    FPTree is created on each workers based on partition id.
                genAllFrequentPatterns(tree_tuple)
                    Get all frequent patterns
                genFreqPatterns(item, prefix, tree)
                    Generate frequent patterns based on item and prefix
        Executing the code on terminal:
        -------------------------------
            Format:
            ------
                python3 parallelFPGrowth.py <inputFile> <outputFile> <minSup> <numWorkers>
            Examples:
            ---------
                python3 parallelFPGrowth.py sampleDB.txt patterns.txt 10.0 3   (minSup will be considered in times of minSup and count of database transactions)
                python3 parallelFPGrowth.py sampleDB.txt patterns.txt 10 3    (minSup will be considered in support count or frequency)
        Sample run of the importing code:
        ---------------------------------
            import PAMI.frequentPattern.pyspark.parallelFPGrowth as alg
            obj = alg.parallelFPGrowth(iFile, minSup, numWorkers)
            obj.startMine()
            frequentPatterns = obj.getPatterns()
            print("Total number of Frequent Patterns:", len(frequentPatterns))
            obj.save(oFile)
            Df = obj.getPatternInDataFrame()
            memUSS = obj.getMemoryUSS()
            print("Total Memory in USS:", memUSS)
            memRSS = obj.getMemoryRSS()
            print("Total Memory in RSS", memRSS)
            run = obj.getRuntime()
            print("Total ExecutionTime in seconds:", run)
        Credits:
        --------
            The complete program was written by Yudai Masu under the supervision of Professor Rage Uday Kiran.
        """
    _minSup = float()
    _numPartitions = int()
    _startTime = float()
    _endTime = float()
    _finalPatterns = dict()
    _FPList = list()
    _iFile = " "
    _oFile = " "
    _sep = " "
    _memoryUSS = float()
    _memoryRSS = float()
    _lno = int()

    def __init__(self, iFile, minSup, numWorkers, sep='\t'):
        super().__init__(iFile, minSup, int(numWorkers), sep)

    def startMine(self):
        """Frequent pattern mining process will start from here"""

        self._startTime = _ab._time.time()

        conf = SparkConf().setAppName("Parallel FPGrowth").setMaster("local[*]")
        sc = SparkContext(conf=conf)

        rdd = sc.textFile(self._iFile, self._numPartitions) \
            .map(lambda x: x.rstrip().split('\t')) \
            .persist()

        self._lno = rdd.count()
        self._minSup = self._convert(self._minSup)

        freqItems = rdd.flatMap(lambda trans: [(item, 1) for item in trans]) \
            .reduceByKey(add) \
            .filter(lambda x: x[1] >= self._minSup) \
            .sortBy(lambda x: x[1], ascending=False) \
            .collect()
        self._finalPatterns = dict(freqItems)
        self._FPList = [x[0] for x in freqItems]
        rank = dict([(item, index) for (index, item) in enumerate(self._FPList)])

        workByPartition = rdd.flatMap(lambda x: self.genCondTransaction(x, rank)).groupByKey()

        trees = workByPartition.foldByKey(_Tree(), lambda tree, data: self.buildTree(tree, data))
        freqPatterns = trees.flatMap(lambda tree_tuple: self.genAllFrequentPatterns(tree_tuple))
        result = freqPatterns.map(
            lambda ranks_count: (tuple([self._FPList[z] for z in ranks_count[0]]), ranks_count[1])) \
            .collect()

        self._finalPatterns.update(dict(result))

        temp = {}
        for pattern, v in self._finalPatterns.items():
            s = ""
            if isinstance(pattern, str):
                s += pattern + '\t'
            else:
                for item in pattern:
                    s += item + '\t'
            temp[s] = v
        self._finalPatterns = temp

        self._endTime = _ab._time.time()
        process = _ab._psutil.Process(_ab._os.getpid())
        self._memoryUSS = process.memory_full_info().uss
        self._memoryRSS = process.memory_info().rss
        sc.stop()

        print("Frequent patterns were generated successfully using Parallel FPGrowth algorithm")

    def getPartitionId(self, value):
        """
            Get partition id of item
            :param value: int
            :return: int
        """
        return value % self._numPartitions

    def genCondTransaction(self, transaction, rank):
        """
            Generate conditional transactions from transaction
            :param transaction : list
            :param rank: dict
            :return: list
        """
        newTrans = [rank[item] for item in transaction if item in rank.keys()]
        newTrans = sorted(newTrans)
        condTrans = {}
        for i in reversed(newTrans):
            partition = self.getPartitionId(i)
            if partition not in condTrans:
                condTrans[partition] = newTrans[:newTrans.index(i) + 1]
        return [x for x in condTrans.items()]

    @staticmethod
    def buildTree(tree, data):
        """
            Build tree from data
            :param tree: Tree
            :param data: list
            :return: tree
        """
        for trans in data:
            tree.addTransaction(trans, 1)
        return tree

    def genAllFrequentPatterns(self, tree_tuple):
        """
            Generate all frequent patterns
            :param tree_tuple: (partition id, tree)
            :return: dict
        """
        itemList = sorted(tree_tuple[1].itemCount.items(), key=lambda x: x[1])
        itemList = [x[0] for x in itemList]
        freqPatterns = {}
        for item in itemList:
            if self.getPartitionId(item) == tree_tuple[0]:
                freqPatterns.update(self.genFreqPatterns(item, [item], tree_tuple[1]))
        return freqPatterns.items()

    def genFreqPatterns(self, item, prefix, tree):
        """
            Generate new frequent patterns based on item
            :param item: item
            :param prefix: prefix frequent pattern
            :param tree: tree
            :return:
        """
        condTree = tree.generateConditionalTree(item)
        freqPatterns = {}
        freqItems = {}
        for i in condTree.nodeLink.keys():
            freqItems[i] = 0
            for node in condTree.nodeLink[i]:
                freqItems[i] += node.count
        freqItems = {key: value for key, value in freqItems.items() if value >= self._minSup}

        for i in freqItems:
            pattern = prefix + [i]
            freqPatterns[tuple(pattern)] = freqItems[i]
            freqPatterns.update(self.genFreqPatterns(i, pattern, condTree))
        return freqPatterns

    def getMemoryUSS(self):
        """Total amount of USS memory consumed by the mining process will be retrieved from this function
        :return: returning USS memory consumed by the mining process
        :rtype: float
        """

        return self._memoryUSS

    def getMemoryRSS(self):
        """Total amount of RSS memory consumed by the mining process will be retrieved from this function
        :return: returning RSS memory consumed by the mining process
        :rtype: float
        """

        return self._memoryRSS

    def getRuntime(self):
        """Calculating the total amount of runtime taken by the mining process
        :return: returning total amount of runtime taken by the mining process
        :rtype: float
        """

        return self._endTime - self._startTime

    def getPatternsAsDataFrame(self):
        """Storing final frequent patterns in a dataframe
        :return: returning frequent patterns in a dataframe
        :rtype: pd.DataFrame
        """

        dataFrame = {}
        data = []
        for a, b in self._finalPatterns.items():
            data.append([a.replace('\t', ' '), b])
            dataFrame = _ab._pd.DataFrame(data, columns=['Patterns', 'Support'])
        return dataFrame

    def save(self, outFile):
        """Complete set of frequent patterns will be loaded in to a output file
        :param outFile: name of the output file
        :type outFile: file
        """
        self._oFile = outFile
        writer = open(self._oFile, 'w+')
        for x, y in self._finalPatterns.items():
            s1 = x.strip() + ":" + str(y)
            writer.write("%s \n" % s1)

    def getPatterns(self):
        """
        Function to send the set of frequent patterns after completion of the mining process
        :return: returning frequent patterns
        :rtype: dict
        """
        return self._finalPatterns

    def _convert(self, value):
        """
        To convert the user specified minSup value
        :param value: user specified minSup value
        :return: converted type
        """
        if type(value) is int:
            value = int(value)
        elif type(value) is float:
            value = (self._lno * value)
        elif type(value) is str:
            if '.' in value:
                value = float(value)
                value = (self._lno * value)
            else:
                value = int(value)
        else:
            print("minSup is not correct")
        return value

    def printResults(self):
        print("Total number of Frequent Patterns:", len(self.getPatterns()))
        print("Total Memory in USS:", self.getMemoryUSS())
        print("Total Memory in RSS", self.getMemoryRSS())
        print("Total ExecutionTime in ms:", self.getRuntime())


if __name__ == "__main__":
    _ap = str()
    if len(_ab._sys.argv) == 5 or len(_ab._sys.argv) == 6:
        if len(_ab._sys.argv) == 6:
            _ap = parallelFPGrowth(_ab._sys.argv[1], _ab._sys.argv[3], _ab._sys.argv[4], _ab._sys.argv[5])
        if len(_ab._sys.argv) == 5:
            _ap = parallelFPGrowth(_ab._sys.argv[1], _ab._sys.argv[3], _ab._sys.argv[4])
        _ap.startMine()
        print("Total number of Frequent Patterns:", len(_ap.getPatterns()))
        _ap.save(_ab._sys.argv[2])
        print("Total Memory in USS:", _ap.getMemoryUSS())
        print("Total Memory in RSS",  _ap.getMemoryRSS())
        print("Total ExecutionTime in ms:", _ap.getRuntime())
    else:
        print("Error! The number of input parameters do not match the total number of parameters provided")
