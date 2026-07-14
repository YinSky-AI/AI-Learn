<template>
  <div class="app-container">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="20" class="mb8">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-info">
              <div class="stat-label">总用户数</div>
              <div class="stat-value">{{ overview.totalUsers }}</div>
            </div>
            <el-icon class="stat-icon" :size="48" color="#409EFF"><User /></el-icon>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-info">
              <div class="stat-label">总课程数</div>
              <div class="stat-value">{{ overview.totalCourses }}</div>
            </div>
            <el-icon class="stat-icon" :size="48" color="#67C23A"><Reading /></el-icon>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-info">
              <div class="stat-label">总学习时长(h)</div>
              <div class="stat-value">{{ overview.totalLearningHours }}</div>
            </div>
            <el-icon class="stat-icon" :size="48" color="#E6A23C"><Timer /></el-icon>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-info">
              <div class="stat-label">总完成课时数</div>
              <div class="stat-value">{{ overview.totalCompletedLessons }}</div>
            </div>
            <el-icon class="stat-icon" :size="48" color="#F56C6C"><Finished /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 课程报名排行榜 -->
    <el-card shadow="hover" class="mb8">
      <template #header>
        <span>课程报名排行榜</span>
      </template>
      <el-table :data="rankingList" v-loading="rankingLoading">
        <el-table-column label="排名" align="center" width="80">
          <template #default="scope">
            <el-tag
              v-if="scope.$index < 3"
              :type="scope.$index === 0 ? 'danger' : scope.$index === 1 ? 'warning' : ''"
              round
            >{{ scope.$index + 1 }}</el-tag>
            <span v-else>{{ scope.$index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="课程名称" align="center" prop="courseName" :show-overflow-tooltip="true" />
        <el-table-column label="学科" align="center" prop="subject" width="100">
          <template #default="scope">
            {{ subjectMap[scope.row.subject] || scope.row.subject }}
          </template>
        </el-table-column>
        <el-table-column label="报名人数" align="center" prop="enrollmentCount" width="120" />
      </el-table>
    </el-card>

    <!-- 学科分布 -->
    <el-card shadow="hover">
      <template #header>
        <span>学科分布</span>
      </template>
      <div v-loading="subjectLoading" class="subject-dist">
        <div v-for="(item, index) in subjectDistList" :key="index" class="subject-item">
          <div class="subject-header">
            <span class="subject-name">{{ subjectMap[item.subject] || item.subject }}</span>
            <span class="subject-count">{{ item.count }} 门课程</span>
          </div>
          <el-progress
            :percentage="getSubjectPercentage(item.count)"
            :color="subjectColors[index % subjectColors.length]"
            :stroke-width="20"
            :text-inside="true"
          />
        </div>
        <el-empty v-if="!subjectLoading && subjectDistList.length === 0" description="暂无数据" />
      </div>
    </el-card>
  </div>
</template>

<script setup name="Stats">
import { getOverview, getCourseRanking, getSubjectDist } from "@/api/learning/stats";

const { proxy } = getCurrentInstance();

/** 学科映射 */
const subjectMap = {
  math: '数学',
  chinese: '语文',
  english: '英语',
  science: '科学',
  history: '历史'
};

/** 学科进度条颜色 */
const subjectColors = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399'];

/** 概览数据 */
const overview = ref({
  totalUsers: 0,
  totalCourses: 0,
  totalLearningHours: 0,
  totalCompletedLessons: 0
});

/** 课程报名排行 */
const rankingList = ref([]);
const rankingLoading = ref(false);

/** 学科分布 */
const subjectDistList = ref([]);
const subjectLoading = ref(false);

/** 计算学科百分比 */
function getSubjectPercentage(count) {
  const total = subjectDistList.value.reduce((sum, item) => sum + item.count, 0);
  if (total === 0) return 0;
  return Math.round((count / total) * 100);
}

/** 获取概览数据 */
function fetchOverview() {
  getOverview().then(response => {
    overview.value = response.data;
  });
}

/** 获取课程报名排行 */
function fetchCourseRanking() {
  rankingLoading.value = true;
  getCourseRanking({ top: 10 }).then(response => {
    rankingList.value = response.data;
    rankingLoading.value = false;
  }).catch(() => {
    rankingLoading.value = false;
  });
}

/** 获取学科分布 */
function fetchSubjectDist() {
  subjectLoading.value = true;
  getSubjectDist().then(response => {
    subjectDistList.value = response.data;
    subjectLoading.value = false;
  }).catch(() => {
    subjectLoading.value = false;
  });
}

onMounted(() => {
  fetchOverview();
  fetchCourseRanking();
  fetchSubjectDist();
});
</script>

<style scoped>
.stat-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
}
.stat-info {
  flex: 1;
}
.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}
.stat-icon {
  opacity: 0.8;
}
.subject-dist {
  padding: 10px 0;
}
.subject-item {
  margin-bottom: 20px;
}
.subject-item:last-child {
  margin-bottom: 0;
}
.subject-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.subject-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}
.subject-count {
  font-size: 14px;
  color: #909399;
}
</style>