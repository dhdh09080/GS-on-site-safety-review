# ----------------------------------------
        # 탭 1: 신규 점수 입력 (대분류 탭 적용)
        # ----------------------------------------
        with tab1:
            st.subheader("📝 현장 세부 심사 입력")
            template_df = load_template()
            
            with st.form("detail_input_form"):
                col1, col2 = st.columns(2)
                with col1: site_name = st.text_input("현장명")
                with col2: site_type = st.selectbox("현장 분류", ["건축", "인프라", "플랜트"])
                
                st.write("---")
                
                # 대장님이 요청하신 10가지 대분류 리스트
                main_categories = [
                    "1. 방침 수립, 조직상황, 성과평가, 내부심사",
                    "2. 인력 및 예산",
                    "3. 위험성평가 및 이행",
                    "4. 종사자 의견 청취 및 개선 조치",
                    "5. 안전보건교육",
                    "6. 비상 시 대응 계획 및 사고관리",
                    "7. 계획 수립",
                    "8. 회의 및 점검",
                    "9. 장비 안전관리 (건기법 포함)",
                    "10. 보건관리"
                ]
                
                # Streamlit 탭 생성
                input_tabs = st.tabs(main_categories)
                input_data = {}
                
                for i, category in enumerate(main_categories):
                    with input_tabs[i]:
                        st.markdown(f"#### {category}")
                        
                        # 해당 대분류에 속하는 항목만 필터링해서 보여주기
                        if not template_df.empty and 'category' in template_df.columns:
                            filtered_df = template_df[template_df['category'] == category]
                            
                            if filtered_df.empty:
                                st.info("이 분류에 등록된 평가 항목이 아직 없습니다. '점수표 설정' 탭에서 항목을 추가해주세요.")
                            else:
                                for index, row in filtered_df.iterrows():
                                    st.markdown(f"**🔹 {row['item_name']}** (배점: {row['max_score']}점)")
                                    
                                    c1, c2 = st.columns([3, 1])
                                    with c2: 
                                        is_na = st.checkbox(f"해당없음", key=f"na_{row['id']}")
                                    with c1: 
                                        score = st.number_input("점수 입력", min_value=0.0, max_value=float(row['max_score']), step=0.5, key=f"score_{row['id']}", disabled=is_na)
                                    
                                    input_data[row['id']] = {"score": score, "is_na": is_na, "max": row['max_score']}
                                    st.write("---")

                st.write("") # 간격 띄우기
                if st.form_submit_button("✅ 전체 데이터 최종 저장", use_container_width=True):
                    if site_name:
                        total_score_earned = 0
                        total_max_possible = 0
                        
                        for item_id, data in input_data.items():
                            if not data["is_na"]: 
                                total_score_earned += data["score"]
                                total_max_possible += data["max"]
                                
                        final_score = (total_score_earned / total_max_possible * 100) if total_max_possible > 0 else 0
                        final_score = round(final_score, 1)

                        supabase.table("audit_results").insert({
                            "site_name": site_name,
                            "site_type": site_type,
                            "score": final_score,
                            "details": json.dumps(input_data)
                        }).execute()
                        
                        st.success(f"'{site_name}' 데이터가 저장되었습니다! (최종 환산점수: {final_score}점)")
                    else:
                        st.error("현장명을 입력해주세요.")

        # ----------------------------------------
        # 탭 3: 점수표(템플릿) 설정 (대분류 선택 기능 추가)
        # ----------------------------------------
        with tab3:
            st.subheader("⚙️ 점수표 항목 자유 수정")
            st.write("대분류를 정확히 맞춰야 입력 탭에 정상적으로 표시됩니다.")
            
            temp_df = load_template()
            if temp_df.empty:
                temp_df = pd.DataFrame(columns=['category', 'item_name', 'max_score'])
            else:
                temp_df = temp_df[['category', 'item_name', 'max_score']]
                
            # 에디터에서 대분류를 드롭다운으로 선택할 수 있게 설정
            edited_df = st.data_editor(
                temp_df, 
                num_rows="dynamic", 
                use_container_width=True,
                column_config={
                    "category": st.column_config.SelectboxColumn(
                        "대분류 (Category)", 
                        options=main_categories,
                        required=True
                    ),
                    "item_name": st.column_config.TextColumn("세부 평가 항목명", required=True),
                    "max_score": st.column_config.NumberColumn("최대 배점", min_value=0, required=True)
                }
            )
            
            if st.button("💾 변경사항 DB에 완전 저장"):
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                new_records = edited_df.to_dict('records')
                if new_records:
                    supabase.table("checklist_template").insert(new_records).execute()
                st.success("점수표가 새롭게 업데이트 되었습니다!")
                st.rerun()
