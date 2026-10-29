<template>
  <el-dialog v-model="visible" title="评价商品" width="560px" @closed="reset">
    <div v-if="order" class="o-info">
      <div class="o-title">{{ order.product_title }}</div>
      <div class="o-meta dim num">订单 {{ order.order_no }} · ¥{{ order.total_amount }}</div>
    </div>

    <el-form label-width="76px">
      <el-form-item label="总体评分" required>
        <el-rate v-model="form.rating" :max="5" show-text :texts="['很差', '较差', '一般', '满意', '非常满意']" />
      </el-form-item>
      <el-form-item label="快捷标签">
        <div class="tags">
          <span v-for="t in TAG_POOL" :key="t" class="tg" :class="{ on: form.tags.includes(t) }"
                @click="toggleTag(t)">{{ t }}</span>
        </div>
      </el-form-item>
      <el-form-item label="评价内容">
        <el-input v-model="form.content" type="textarea" :rows="4" maxlength="1000" show-word-limit
                  placeholder="果实大小、干燥度、杂质、物流速度等真实感受，会帮助其他买家判断" />
      </el-form-item>
      <el-form-item label="实拍图">
        <div class="uploads">
          <div v-for="(u, i) in form.images" :key="i" class="up-img" :style="{ backgroundImage: `url(${u})` }">
            <span class="del" @click="form.images.splice(i, 1)">×</span>
          </div>
          <el-upload v-if="form.images.length < 6" :show-file-list="false" accept="image/*"
                     :http-request="upload">
            <div class="up-add">＋</div>
          </el-upload>
        </div>
      </el-form-item>
      <el-form-item label="匿名">
        <el-switch v-model="form.anonymous" />
        <span class="dim" style="margin-left:8px">匿名后仅显示「杭**」</span>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">提交评价</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createReview, uploadImage } from '../../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  order: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'done'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const TAG_POOL = ['果形饱满', '干燥度好', '杂质少', '包装结实', '物流快', '与描述一致', '性价比高']
const form = reactive({ rating: 5, content: '', tags: [], images: [], anonymous: false })
const saving = ref(false)

function toggleTag(t) {
  const i = form.tags.indexOf(t)
  if (i >= 0) form.tags.splice(i, 1)
  else if (form.tags.length < 6) form.tags.push(t)
}

async function upload({ file }) {
  const r = await uploadImage(file, 'after-sale/evidence')
  form.images.push(r.url)
}

async function submit() {
  if (!form.rating) return ElMessage.warning('请先打分')
  saving.value = true
  try {
    await createReview(props.order.order_id, { ...form })
    ElMessage.success('评价已提交，感谢反馈')
    visible.value = false
    emit('done')
  } finally {
    saving.value = false
  }
}

function reset() {
  form.rating = 5
  form.content = ''
  form.tags = []
  form.images = []
  form.anonymous = false
}

watch(() => props.modelValue, (v) => { if (v) reset() })
</script>

<style scoped>
.o-info { background: var(--brand-soft); border-radius: 8px; padding: 10px 12px; margin-bottom: 14px; }
.o-title { font-size: 13.5px; font-weight: 600; }
.o-meta { font-size: 12px; margin-top: 3px; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tg { font-size: 12.5px; padding: 3px 10px; border: 1px solid var(--line); border-radius: 14px;
  cursor: pointer; color: var(--ink-2); transition: all .15s; }
.tg:hover { border-color: var(--brand); color: var(--brand); }
.tg.on { background: var(--brand); border-color: var(--brand); color: #fff; }
.uploads { display: flex; gap: 8px; flex-wrap: wrap; }
.up-img { width: 72px; height: 72px; border-radius: 8px; border: 1px solid var(--line);
  background: #f3ebe4 center/cover no-repeat; position: relative; }
.up-img .del { position: absolute; right: -6px; top: -6px; width: 18px; height: 18px; border-radius: 50%;
  background: var(--brand); color: #fff; font-size: 13px; line-height: 18px; text-align: center; cursor: pointer; }
.up-add { width: 72px; height: 72px; border: 1px dashed var(--line); border-radius: 8px; display: grid;
  place-items: center; font-size: 20px; color: var(--ink-4); cursor: pointer; }
.up-add:hover { border-color: var(--brand); color: var(--brand); }
</style>
