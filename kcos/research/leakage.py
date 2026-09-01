class LeakageGuard:
    def verify_split(self,train_end,test_start):
        if train_end>=test_start: return False,'train_test_overlap'
        return True,'ok'
    def verify_feature_timestamps(self,feature_times,label_time):
        bad=[t for t in feature_times if t>label_time]; return (not bad,'ok' if not bad else 'future_feature_timestamp')
