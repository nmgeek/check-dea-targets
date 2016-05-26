# Mark when student test scores met targets on DEA tests. See README
# on github for details.
import glob, os
import numpy as np
import pandas as pd

SUBJECT_CATEGORY = {
    'math':[
        'Algebra 1',
        'Algebra 2',
        'Geometry',
        'Mathematics',
    ],
    'language':[
        'English 1',
        'English 2',
        'Reading Language Arts',
    ]
}
SUBJECT_LONG_TO_SHORT = {
    'HS Algebra 1': 'Algebra 1',
    'HS Algebra 2': 'Algebra 2',
    'HS Geometry': 'Geometry',
    'HS English 2':'English 2',
    'HS English 1':'English 1',
    '8 Reading Language Arts':'8th Grade Reading',
    '7 Reading Language Arts':'7th Grade Reading',
    '9 Mathematics':'9th Grade Math',
    '7 Mathematics':'7th Grade Math',
    '8 Mathematics':'8th Grade Math',
}
TARGET_SUBJECTS = {
    'math':[
        'Algebra 1',
        'Algebra 2',
        'Geometry',
        '7th Grade Math',
        '8th Grade Math',
        '9th Grade Math',
    ],
    'language':[
        'English 1',
        'English 2',
        '7th Grade Reading',
        '8th Grade Reading',
    ],
}
# columns to load from student data files
READ_COLS = [
    'Student ID', 
    'Grade',
    'Test Period:Opening Test Date',
    'Scale Score', 
    'Achievement Level',
]
# columns which repeat per test period
SUFFIX_COLS = [
    'Grade',
    'Test',
    'Scale Score', 
    'Level',
]
TESTS = ['A:20150824','B:20151102','C:20160201']
YEAR = '2016'
CSV_DIR = '/mnt/nasshare/DEA data 2016/'

def processCategory(category):
    #
    # Read csv files with student data.  Each file has its subject in the name.
    #
    subjectDfs = []
    for subject in SUBJECT_CATEGORY[category]:
        fname = glob.glob(CSV_DIR+subject+' '+YEAR+'.csv')[0]
        subjectDf = pd.read_csv(fname, usecols=READ_COLS, index_col=2)
        subjectDf.columns = SUFFIX_COLS
        subjectDf.set_index('Test', append=True, inplace=True)
        subjectDf['Subject'] = subject
        subjectDfs += [subjectDf]

    # merge all subjects into one dataframe
    allSubjectDf = pd.concat(subjectDfs).swaplevel(0, 1, axis=0)

    #
    # Denormalize for each test period so all periods occur in each row
    #
    testDfs = []
    for test in TESTS:
        suffix = ' '+test.split(':')[0]
        testDf = allSubjectDf.loc[test]
        testDf.columns = [x+suffix for x in testDf.columns]
        testDfs += [testDf]
    categoryDf = testDfs[0].join(testDfs[1:], how='outer')
    # tbd
    # categoryDf = joinedDf.swaplevel(0, 1, axis=0)

    #
    # load target score tables
    #
    # File Headers look like:
    # Scale Score,Growth points,Target score
    #
    scoreToTarget = {}
    for subject in TARGET_SUBJECTS[category]:
        fname = CSV_DIR+'Target score tables '+subject+'.csv'
        targetDf = pd.read_csv(fname, usecols=[1,3], header=2)
        subScoreToTarget = {}
        for row in range(len(targetDf)-1):
            ts = targetDf['Target score'][row]
            if pd.notnull(ts):
                targetScore = ts
            # fill in internal values in range for easy lookup, later
            for baseScore in range(int(targetDf['Scale Score'][row]), 
                                   int(targetDf['Scale Score'][row+1])):
                subScoreToTarget[baseScore] = int(targetScore)
        scoreToTarget[subject] = subScoreToTarget

    #
    # add result columns with default values
    #
    dlen = len(categoryDf)
    categoryDf.loc[:,'Base Score'] = np.zeros(dlen)*np.nan
    categoryDf.loc[:,'Target Score'] = np.zeros(dlen)*np.nan
    categoryDf.loc[:,'Met Target'] = np.zeros(dlen, dtype=bool)

    # Look in A, B, or C test period for fields like grade and
    # subject.  All three instances should be the same but when they
    # are not populated if student did not take test during a period.
    # And rarely a student might move up a grade level between tests.
    def lookupABC(row, field):
        prefix = field.title()+' '
        result = row[prefix+'A']
        if pd.isnull(result):
            result = row[prefix+'B']
            if pd.isnull(result):
                result = row[prefix+'C']
        if pd.notnull(row[prefix+'B']):
            if result != row[prefix+'B']:
                return None
        if pd.notnull(row[prefix+'C']):
            if result != row[prefix+'C']:
                return None
        return str(result)

    #
    # assign result values
    #
    for id,row in categoryDf.iterrows():
        # base score is lower of first two tests
        baseScore = np.nanmin((row['Scale Score A'], row['Scale Score B']))
        if pd.isnull(baseScore):
            print id,'has no test data for first two tests in',category
            continue
        baseScore = int(baseScore)
        grade = lookupABC(row, 'Grade')
        if pd.isnull(grade):
                print id,'took tests from multiple grade levels in',category
                continue
        subject = lookupABC(row, 'Subject')
        subject = SUBJECT_LONG_TO_SHORT[grade+' '+subject]

        # find target in lookup table
        targetScore = scoreToTarget[subject][baseScore]

        # store results for this student
        categoryDf.loc[id,'Base Score'] = baseScore
        categoryDf.loc[id,'Target Score'] = targetScore
        if targetScore <= np.nanmax((row['Scale Score B'], row['Scale Score C'])):
            categoryDf.loc[id,'Met Target'] = True

    # save results
    categoryDf.to_csv(category+'.csv')

for category in ['math','language']:
    processCategory(category)

