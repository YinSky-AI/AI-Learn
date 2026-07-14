<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="课程名称" prop="courseName">
        <el-input
          v-model="queryParams.courseName"
          placeholder="请输入课程名称"
          clearable
          style="width: 200px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="学科" prop="subject">
        <el-select v-model="queryParams.subject" placeholder="请选择学科" clearable style="width: 200px">
          <el-option
            v-for="dict in subjectOptions"
            :key="dict.value"
            :label="dict.label"
            :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="难度" prop="difficulty">
        <el-select v-model="queryParams.difficulty" placeholder="请选择难度" clearable style="width: 200px">
          <el-option
            v-for="dict in difficultyOptions"
            :key="dict.value"
            :label="dict.label"
            :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="isActive">
        <el-select v-model="queryParams.isActive" placeholder="课程状态" clearable style="width: 200px">
          <el-option
            v-for="dict in statusOptions"
            :key="dict.value"
            :label="dict.label"
            :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" :columns="columns"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="courseList">
      <el-table-column label="课程ID" align="center" prop="courseId" width="80" v-if="columns[0].visible" />
      <el-table-column label="封面" align="center" prop="coverUrl" width="80" v-if="columns[1].visible">
        <template #default="scope">
          <image-preview :src="scope.row.coverUrl" :width="50" :height="50" />
        </template>
      </el-table-column>
      <el-table-column label="课程名称" align="center" prop="courseName" :show-overflow-tooltip="true" v-if="columns[2].visible" />
      <el-table-column label="学科" align="center" prop="subject" width="80" v-if="columns[3].visible">
        <template #default="scope">
          {{ subjectMap[scope.row.subject] || scope.row.subject }}
        </template>
      </el-table-column>
      <el-table-column label="难度" align="center" prop="difficulty" width="80" v-if="columns[4].visible">
        <template #default="scope">
          {{ difficultyMap[scope.row.difficulty] || scope.row.difficulty }}
        </template>
      </el-table-column>
      <el-table-column label="年龄段" align="center" prop="ageGroup" width="80" v-if="columns[5].visible" />
      <el-table-column label="总课时" align="center" prop="totalLessons" width="80" v-if="columns[6].visible" />
      <el-table-column label="时长(分钟)" align="center" prop="duration" width="100" v-if="columns[7].visible" />
      <el-table-column label="报名人数" align="center" prop="enrollmentCount" width="100" v-if="columns[8].visible" />
      <el-table-column label="评分" align="center" prop="rating" width="80" v-if="columns[9].visible" />
      <el-table-column label="状态" align="center" prop="isActive" width="80" v-if="columns[10].visible">
        <template #default="scope">
          <el-switch
            v-model="scope.row.isActive"
            :active-value="true"
            :inactive-value="false"
            @change="handleStatusChange(scope.row)"
          ></el-switch>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" width="160" v-if="columns[11].visible">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="150" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleDetail(scope.row)">详情</el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 课程详情弹窗 -->
    <el-dialog :title="'课程详情 - ' + (courseDetail.courseName || '')" v-model="detailOpen" width="800px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="课程ID">{{ courseDetail.courseId }}</el-descriptions-item>
        <el-descriptions-item label="课程名称">{{ courseDetail.courseName }}</el-descriptions-item>
        <el-descriptions-item label="学科">{{ subjectMap[courseDetail.subject] || courseDetail.subject }}</el-descriptions-item>
        <el-descriptions-item label="难度">{{ difficultyMap[courseDetail.difficulty] || courseDetail.difficulty }}</el-descriptions-item>
        <el-descriptions-item label="年龄段">{{ courseDetail.ageGroup }}</el-descriptions-item>
        <el-descriptions-item label="总课时">{{ courseDetail.totalLessons }}</el-descriptions-item>
        <el-descriptions-item label="时长(分钟)">{{ courseDetail.duration }}</el-descriptions-item>
        <el-descriptions-item label="报名人数">{{ courseDetail.enrollmentCount }}</el-descriptions-item>
        <el-descriptions-item label="评分">{{ courseDetail.rating }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="courseDetail.isActive ? 'success' : 'danger'">
            {{ courseDetail.isActive ? '启用' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="课程描述" :span="2">{{ courseDetail.description }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ parseTime(courseDetail.createTime) }}</el-descriptions-item>
      </el-descriptions>

      <!-- 课时列表 -->
      <el-divider content-position="left">课时列表</el-divider>
      <el-table :data="courseDetail.lessons" border style="width: 100%">
        <el-table-column label="课时序号" align="center" prop="lessonIndex" width="100" />
        <el-table-column label="课时标题" align="center" prop="title" :show-overflow-tooltip="true" />
        <el-table-column label="时长(分钟)" align="center" prop="duration" width="120" />
        <el-table-column label="排序" align="center" prop="sortOrder" width="80" />
      </el-table>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="detailOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Course">
import { listCourse, getCourse, changeCourseStatus, delCourse } from "@/api/learning/course";

const { proxy } = getCurrentInstance();

/** 学科映射 */
const subjectMap = {
  math: '数学',
  chinese: '语文',
  english: '英语',
  science: '科学',
  history: '历史'
};
/** 难度映射 */
const difficultyMap = {
  beginner: '入门',
  intermediate: '进阶',
  advanced: '高级'
};
/** 学科下拉选项 */
const subjectOptions = ref([
  { label: '数学', value: 'math' },
  { label: '语文', value: 'chinese' },
  { label: '英语', value: 'english' },
  { label: '科学', value: 'science' },
  { label: '历史', value: 'history' }
]);
/** 难度下拉选项 */
const difficultyOptions = ref([
  { label: '入门', value: 'beginner' },
  { label: '进阶', value: 'intermediate' },
  { label: '高级', value: 'advanced' }
]);
/** 状态下拉选项 */
const statusOptions = ref([
  { label: '启用', value: true },
  { label: '停用', value: false }
]);

const courseList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const detailOpen = ref(false);
const courseDetail = ref({});

// 列显隐信息
const columns = ref([
  { key: 0, label: `课程ID`, visible: true },
  { key: 1, label: `封面`, visible: true },
  { key: 2, label: `课程名称`, visible: true },
  { key: 3, label: `学科`, visible: true },
  { key: 4, label: `难度`, visible: true },
  { key: 5, label: `年龄段`, visible: true },
  { key: 6, label: `总课时`, visible: true },
  { key: 7, label: `时长(分钟)`, visible: true },
  { key: 8, label: `报名人数`, visible: true },
  { key: 9, label: `评分`, visible: true },
  { key: 10, label: `状态`, visible: true },
  { key: 11, label: `创建时间`, visible: true },
]);

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    courseName: undefined,
    subject: undefined,
    difficulty: undefined,
    isActive: undefined
  }
});

const { queryParams } = toRefs(data);

/** 查询课程列表 */
function getList() {
  loading.value = true;
  listCourse(queryParams.value).then(response => {
    courseList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}
/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}
/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}
/** 课程状态修改 */
function handleStatusChange(row) {
  let text = row.isActive ? "启用" : "停用";
  proxy.$modal.confirm('确认要"' + text + '""' + row.courseName + '"课程吗?').then(function () {
    return changeCourseStatus({ courseId: row.courseId, isActive: row.isActive });
  }).then(() => {
    proxy.$modal.msgSuccess(text + "成功");
  }).catch(function () {
    row.isActive = !row.isActive;
  });
}
/** 详情按钮操作 */
function handleDetail(row) {
  getCourse(row.courseId).then(response => {
    courseDetail.value = response.data;
    detailOpen.value = true;
  });
}
/** 删除按钮操作 */
function handleDelete(row) {
  const courseId = row.courseId;
  proxy.$modal.confirm('是否确认删除课程编号为"' + courseId + '"的数据项？').then(function () {
    return delCourse(courseId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

getList();
</script>