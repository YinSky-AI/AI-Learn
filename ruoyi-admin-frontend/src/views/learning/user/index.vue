<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="昵称/邮箱" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="请输入昵称或邮箱"
          clearable
          style="width: 200px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="年龄段" prop="ageGroup">
        <el-select v-model="queryParams.ageGroup" placeholder="请选择年龄段" clearable style="width: 200px">
          <el-option
            v-for="dict in ageGroupOptions"
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
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="userList">
      <el-table-column label="用户ID" align="center" prop="userId" width="80" />
      <el-table-column label="昵称" align="center" prop="nickname" :show-overflow-tooltip="true" />
      <el-table-column label="邮箱" align="center" prop="email" :show-overflow-tooltip="true" />
      <el-table-column label="年龄段" align="center" prop="ageGroup" width="80">
        <template #default="scope">
          {{ scope.row.ageGroup }}
        </template>
      </el-table-column>
      <el-table-column label="总积分" align="center" prop="totalPoints" width="100" />
      <el-table-column label="连续学习天数" align="center" prop="streakDays" width="120" />
      <el-table-column label="注册时间" align="center" prop="createTime" width="160">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="上次登录" align="center" prop="lastLoginTime" width="160">
        <template #default="scope">
          <span>{{ parseTime(scope.row.lastLoginTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="180" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleDetail(scope.row)">详情</el-button>
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)">编辑</el-button>
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

    <!-- 用户详情弹窗 -->
    <el-dialog title="用户详情" v-model="detailOpen" width="600px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户ID">{{ userDetail.userId }}</el-descriptions-item>
        <el-descriptions-item label="昵称">{{ userDetail.nickname }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ userDetail.email }}</el-descriptions-item>
        <el-descriptions-item label="年龄段">{{ userDetail.ageGroup }}</el-descriptions-item>
        <el-descriptions-item label="总积分">{{ userDetail.totalPoints }}</el-descriptions-item>
        <el-descriptions-item label="连续学习天数">{{ userDetail.streakDays }}</el-descriptions-item>
        <el-descriptions-item label="注册时间" :span="2">{{ parseTime(userDetail.createTime) }}</el-descriptions-item>
        <el-descriptions-item label="上次登录" :span="2">{{ parseTime(userDetail.lastLoginTime) }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="detailOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 编辑用户弹窗 -->
    <el-dialog title="编辑用户" v-model="editOpen" width="500px" append-to-body>
      <el-form ref="editRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="用户ID">
          <el-input v-model="editForm.userId" disabled />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="editForm.nickname" placeholder="请输入昵称" maxlength="30" />
        </el-form-item>
        <el-form-item label="年龄段" prop="ageGroup">
          <el-select v-model="editForm.ageGroup" placeholder="请选择年龄段">
            <el-option
              v-for="dict in ageGroupOptions"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="editOpen = false">取 消</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="PlatformUser">
import { listPlatformUser, getPlatformUser, updatePlatformUser, delPlatformUser } from "@/api/learning/user";

const { proxy } = getCurrentInstance();

/** 年龄段下拉选项 */
const ageGroupOptions = ref([
  { label: '6-8岁', value: '6-8' },
  { label: '9-12岁', value: '9-12' },
  { label: '13-15岁', value: '13-15' }
]);

const userList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const detailOpen = ref(false);
const editOpen = ref(false);
const userDetail = ref({});

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    ageGroup: undefined
  },
  editForm: {},
  editRules: {
    nickname: [{ required: true, message: "昵称不能为空", trigger: "blur" }],
    ageGroup: [{ required: true, message: "年龄段不能为空", trigger: "change" }]
  }
});

const { queryParams, editForm, editRules } = toRefs(data);

/** 查询用户列表 */
function getList() {
  loading.value = true;
  listPlatformUser(queryParams.value).then(response => {
    userList.value = response.rows;
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
/** 详情按钮操作 */
function handleDetail(row) {
  getPlatformUser(row.userId).then(response => {
    userDetail.value = response.data;
    detailOpen.value = true;
  });
}
/** 修改按钮操作 */
function handleUpdate(row) {
  resetEdit();
  getPlatformUser(row.userId).then(response => {
    editForm.value = {
      userId: response.data.userId,
      nickname: response.data.nickname,
      ageGroup: response.data.ageGroup
    };
    editOpen.value = true;
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["editRef"].validate(valid => {
    if (valid) {
      updatePlatformUser(editForm.value).then(response => {
        proxy.$modal.msgSuccess("修改成功");
        editOpen.value = false;
        getList();
      });
    }
  });
}
/** 删除按钮操作 */
function handleDelete(row) {
  const userId = row.userId;
  proxy.$modal.confirm('是否确认删除用户编号为"' + userId + '"的数据项？').then(function () {
    return delPlatformUser(userId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}
/** 重置编辑表单 */
function resetEdit() {
  editForm.value = {
    userId: undefined,
    nickname: undefined,
    ageGroup: undefined
  };
  proxy.resetForm("editRef");
}

getList();
</script>